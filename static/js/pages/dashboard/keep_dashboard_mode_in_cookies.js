// static/js/pages/dashboard/keep_dashboard_mode_in_cookies.js

(function() {
    const select = document.getElementById("dashboard_mode");
    if (!select) return;

    select.addEventListener("change", function() {
        const mode = select.value;

        // Persist for 90 days
        const maxAge = 60 * 60 * 24 * 90;
        document.cookie = `dashboard_mode=${encodeURIComponent(mode)}; Path=/; Max-Age=${maxAge}; SameSite=Lax`;

        // Reload with ?mode=... so the backend immediately uses it (and link is shareable)
        const url = new URL(window.location.href);
        url.searchParams.set("view", mode);
        window.location.href = url.toString();
    });
})();
