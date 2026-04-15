from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.templatetags.static import static
from django.views.decorators.http import require_GET


PWA_PRIMARY_ORIGIN = "https://work.sitarisolutions.in"


@require_GET
def manifest(request):
    is_primary_host = request.get_host().split(":")[0] == "work.sitarisolutions.in"
    start_url = "/login/"

    # Use a fixed production app id on the real domain, but keep local dev installable.
    app_id = f"{PWA_PRIMARY_ORIGIN}{start_url}" if is_primary_host else start_url

    package_name = getattr(settings, "TWA_ANDROID_PACKAGE_NAME", "")

    data = {
        "name": "Sitari Solutions",
        "short_name": "Sitari",
        "description": "Sitari Solutions employee and service management portal",
        "id": app_id,
        "start_url": start_url,
        "scope": "/",
        "display": "standalone",
        "display_override": ["standalone", "minimal-ui"],
        "background_color": "#f5f8ff",
        "theme_color": "#0a4a8a",
        "icons": [
            {
                "src": static("management/img/app-icon-192.png"),
                "sizes": "192x192",
                "type": "image/png",
            },
            {
                "src": static("management/img/app-icon-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            }
        ],
        "prefer_related_applications": bool(package_name),
        "related_applications": [
            {
                "platform": "play",
                "id": package_name,
            }
        ] if package_name else [],
    }
    response = JsonResponse(data)
    response["Content-Type"] = "application/manifest+json"
    response["Cache-Control"] = "public, max-age=3600"
    return response


@require_GET
def service_worker(request):
    static_prefixes = [
        static("management/img/logo.jpg"),
        static("css/jazzmin_custom.css"),
    ]

    sw_script = "\n".join(
        [
            "const PWA_CACHE = 'sitari-pwa-v1';",
            "const STATIC_ASSETS = [",
            "  '/',",
            "  '/login/',",
            f"  '{static_prefixes[0]}',",
            f"  '{static_prefixes[1]}',",
            "];",
            "",
            "self.addEventListener('install', (event) => {",
            "  event.waitUntil(caches.open(PWA_CACHE).then((cache) => cache.addAll(STATIC_ASSETS)));",
            "  self.skipWaiting();",
            "});",
            "",
            "self.addEventListener('activate', (event) => {",
            "  event.waitUntil(",
            "    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== PWA_CACHE).map((k) => caches.delete(k))))",
            "  );",
            "  self.clients.claim();",
            "});",
            "",
            "self.addEventListener('fetch', (event) => {",
            "  if (event.request.method !== 'GET') {",
            "    return;",
            "  }",
            "",
            "  const url = new URL(event.request.url);",
            "  const isStatic = url.pathname.startsWith('/static/');",
            "",
            "  if (isStatic) {",
            "    event.respondWith(",
            "      caches.match(event.request).then((cached) => {",
            "        return cached || fetch(event.request).then((response) => {",
            "          const cloned = response.clone();",
            "          caches.open(PWA_CACHE).then((cache) => cache.put(event.request, cloned));",
            "          return response;",
            "        });",
            "      })",
            "    );",
            "  }",
            "});",
        ]
    )

    response = HttpResponse(sw_script, content_type="application/javascript")
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@require_GET
def assetlinks(request):
    package_name = getattr(settings, "TWA_ANDROID_PACKAGE_NAME", "")
    fingerprints = getattr(settings, "TWA_SHA256_CERT_FINGERPRINTS", [])

    if not package_name or not fingerprints:
        response = JsonResponse([], safe=False)
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

    statements = [
        {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": package_name,
                "sha256_cert_fingerprints": fingerprints,
            },
        }
    ]

    response = JsonResponse(statements, safe=False)
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response
