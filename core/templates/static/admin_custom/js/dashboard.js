document.addEventListener("DOMContentLoaded", function () {

    // Sidebar toggle
    const btn = document.getElementById("toggleSidebar");
    const sidebar = document.getElementById("sidebar");

    if (btn) {
        btn.addEventListener("click", () => {
            sidebar.classList.toggle("collapsed");
        });
    }

});