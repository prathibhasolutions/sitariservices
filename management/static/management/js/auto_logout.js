let idleSeconds = 0;
function resetIdle() { idleSeconds = 0; }

document.addEventListener('click', resetIdle);
document.addEventListener('mousemove', resetIdle);
document.addEventListener('keypress', resetIdle);

const csrftoken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

setInterval(function () {
    idleSeconds++;
    if (idleSeconds % 60 === 0) {
        console.log(`Idle for ${idleSeconds} seconds`);
    }
    if (idleSeconds >= 300) { // Logout after 5 minutes
        console.log('Idle timeout reached, logging out.');
        fetch('/logout/', {
            method: 'POST',
            headers: {
                "X-CSRFToken": csrftoken,
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: "logout_reason=Employee is not working"
        })
            .then(res => {
                if (res.ok) {
                    window.location.href = "/login/";
                } else {
                    console.error('Logout request failed:', res.statusText);
                }
            })
            .catch(err => console.error('Logout fetch error:', err));
    }
}, 1000);
