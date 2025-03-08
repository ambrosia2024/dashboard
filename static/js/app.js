(function ($) {
    "use strict";

    // Counter Animation
    function counterAnimation() {
        var counterElements = document.querySelectorAll(".counter-value");
        counterElements.forEach(function (element) {
            (function increment() {
                var target = +element.getAttribute("data-target"),
                    count = +element.innerText,
                    incrementValue = target / 250;

                if (incrementValue < 1) incrementValue = 1;

                if (count < target) {
                    element.innerText = (count + incrementValue).toFixed(0);
                    setTimeout(increment, 1);
                } else {
                    element.innerText = target;
                }
            })();
        });
    }

    // Function to apply blue color to the active icon after Feather replaces them
    function applyActiveIconColor() {
        $("#sidebar-menu .active i").css({
            "color": "#1c84ee",
            "stroke": "#1c84ee"
        });
    }

    // Navbar Link Activation
    $("#sidebar-menu a, .navbar-nav a").each(function () {
        var currentUrl = window.location.href.split(/[?#]/)[0];
        if (this.href === currentUrl) {
            $(this).addClass("active")
                .parentsUntil("#sidebar-menu, .navbar-nav")
                .addClass("active");
        }
    });

    // Sidebar Menu Management
    $("#side-menu").metisMenu();
    $(window).on("load", function () {
        var body = document.querySelector("body");

        // Adjust sidebar size based on window width
        if (window.innerWidth >= 1024 && window.innerWidth <= 1366) {
            body.setAttribute("data-sidebar-size", "sm");
        }

        // Activate sidebar items based on URL
        $("#sidebar-menu a").each(function () {
            var currentUrl = window.location.href.split(/[?#]/)[0];
            if (this.href === currentUrl) {
                $(this).addClass("active").parents().addClass("mm-active mm-show");
            }
        });

        // Scroll to active item in sidebar on load if not visible
        if ($("#sidebar-menu .mm-active .active").length) {
            var offset = $("#sidebar-menu .mm-active .active").offset().top;
            if (offset > 300) {
                $(".vertical-menu .simplebar-content-wrapper").animate({ scrollTop: offset - 300 }, "slow");
            }
        }
    });

    // Preloader and Loading Animation
    $(window).on("load", function () {
        $("#status").fadeOut();
        $("#preloader").delay(350).fadeOut("slow");
    });

    // Bootstrap Tooltip, Popover, and Toast Initialisation
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (tooltipElement) {
        new bootstrap.Tooltip(tooltipElement);
    });
    document.querySelectorAll('[data-bs-toggle="popover"]').forEach(function (popoverElement) {
        new bootstrap.Popover(popoverElement);
    });
    document.querySelectorAll(".toast").forEach(function (toastElement) {
        new bootstrap.Toast(toastElement);
    });

    var toastTrigger = document.getElementById("borderedToast1Btn"),
        toastLive = document.getElementById("borderedToast1");

    if (toastTrigger) {
        toastTrigger.addEventListener("click", function () {
            new bootstrap.Toast(toastLive).show();
        });
        toastTrigger.click();
    }

    // Execute counter animation
    counterAnimation();

    // Render Feather Icons and apply active color
    setTimeout(function () {
        feather.replace();
        applyActiveIconColor(); // Apply color to the active icon
    }, 100); // Small delay to ensure Feather icons are replaced

})(jQuery);