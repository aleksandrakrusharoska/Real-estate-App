document.addEventListener("DOMContentLoaded", function () {
    function wireCoverCheckboxes() {
        const coverCheckboxes = document.querySelectorAll(
            'input[type="checkbox"][name$="-is_cover"]'
        );

        coverCheckboxes.forEach((cb) => {
            if (cb.dataset.coverBound === "1") return;
            cb.dataset.coverBound = "1";

            cb.addEventListener("change", function () {
                if (!this.checked) return;

                coverCheckboxes.forEach((other) => {
                    if (other !== this) other.checked = false;
                });
            });
        });
    }

    wireCoverCheckboxes();

    document.body.addEventListener("click", function (e) {
        const btn = e.target.closest(".add-row a, .add-row button");
        if (btn) {
            setTimeout(wireCoverCheckboxes, 50);
        }
    });
});