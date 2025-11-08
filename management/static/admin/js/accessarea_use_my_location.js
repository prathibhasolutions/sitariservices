// Adds a 'Use My Location' button to the AccessArea admin form
(function() {
    function addUseMyLocationButton() {
        var latInput = document.getElementById('id_latitude');
        var lngInput = document.getElementById('id_longitude');
        if (!latInput || !lngInput) return;
        if (document.getElementById('use-my-location-btn')) return;
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.id = 'use-my-location-btn';
        btn.textContent = 'Use My Location';
        btn.style.marginLeft = '10px';
        btn.onclick = function(e) {
            e.preventDefault();
            if (!navigator.geolocation) {
                alert('Geolocation is not supported by your browser.');
                return;
            }
            btn.textContent = 'Locating...';
            navigator.geolocation.getCurrentPosition(function(pos) {
                latInput.value = pos.coords.latitude;
                lngInput.value = pos.coords.longitude;
                btn.textContent = 'Use My Location';
            }, function() {
                alert('Unable to retrieve your location.');
                btn.textContent = 'Use My Location';
            });
        };
        latInput.parentNode.appendChild(btn);
    }
    document.addEventListener('DOMContentLoaded', addUseMyLocationButton);
    // For Django inlines or dynamic admin, also try after a delay
    setTimeout(addUseMyLocationButton, 1000);
})();
