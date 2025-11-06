document.addEventListener("DOMContentLoaded", function () {
    const toolbar   = document.querySelector(".risk-toolbar .card");
    const header    = document.getElementById("page-topbar");
    const container = document.querySelector(".page-content .container-fluid");

    function positionToolbar() {
        if (!toolbar || !container) return;

        const headerH = header ? header.offsetHeight : 20;
        const rect    = container.getBoundingClientRect();
        const styles  = window.getComputedStyle(container);

        const padLeft  = parseFloat(styles.paddingLeft)  || 0;
        const padRight = parseFloat(styles.paddingRight) || 0;

        // fix, no gaps, directly under header
        toolbar.style.position  = "fixed";
        toolbar.style.top       = headerH + "px";                 // ← no +8
        toolbar.style.left      = (rect.left + padLeft) + "px";   // flush with container content
        toolbar.style.width     = (rect.width - padLeft - padRight) + "px";
        toolbar.style.zIndex    = 1200;
        toolbar.style.boxSizing = "border-box";

        // push content down exactly by toolbar height
        const toolbarH = toolbar.offsetHeight;
        container.style.paddingTop = toolbarH + "px";
    }

    positionToolbar();
    window.addEventListener("resize", positionToolbar);
    window.addEventListener("scroll", positionToolbar);
});