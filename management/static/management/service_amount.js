// Show the selected service's amount next to the dropdown, but do not autofill the amount input
document.addEventListener('DOMContentLoaded', function () {
    var serviceSelect = document.querySelector('.service-dropdown');
    var amountDisplay = document.getElementById('service-amount-display');
    if (!serviceSelect || !amountDisplay) return;
    function updateAmountDisplay() {
        var selected = serviceSelect.options[serviceSelect.selectedIndex];
        // Use getAttribute to ensure data-amount is read correctly
        var amount = selected ? selected.getAttribute('data-amount') : null;
        if (selected && selected.value && amount) {
            amountDisplay.textContent = 'Amount: ₹' + amount;
        } else {
            amountDisplay.textContent = '';
        }
    }

    serviceSelect.addEventListener('change', updateAmountDisplay);
    updateAmountDisplay(); // Initial call in case of pre-selected value
});
