function showToast(zprava, typ = 'success') {
    // 1. Najdeme nebo vytvoříme kontejner pro notifikace
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    // 2. Vytvoříme HTML prvek Toastu
    const toast = document.createElement('div');
    toast.className = `toast toast-${typ}`; // Přidá třídu podle typu (success/error)
    
    // Vytvoříme obsah - přidáme malou ikonku podle typu
    const ikona = typ === 'success' ? '✅ ' : '❌ ';
    toast.innerHTML = `<strong>${ikona}</strong> ${zprava}`;

    // 3. Vložíme do kontejneru (zatím mimo obrazovku)
    container.appendChild(toast);

    // 4. Spustíme animaci vyjetí
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);

    // 5. Timer: Po 4 vteřinách notifikaci schováme a odstraníme
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 400); 
    }, 4000);
}

/**
 * Zobrazí stylové potvrzovací okno
 */
async function showConfirm(zprava, tlacitkoText = "Potvrdit") {
    return new Promise((resolve) => {
        // Vytvoření elementů
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal-content">
                <h3 style="margin-bottom: 15px; color: var(--color-accent);">Potvrzení akce</h3>
                <p style="margin-bottom: 10px;">${zprava}</p>
                <div class="modal-buttons">
                    <button class="modal-btn modal-cancel">Zrušit</button>
                    <button class="modal-btn modal-confirm">${tlacitkoText}</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);

        // Animace vyjetí
        setTimeout(() => overlay.classList.add('active'), 10);

        // Obsluha tlačítek
        overlay.querySelector('.modal-confirm').onclick = () => {
            overlay.classList.remove('active');
            setTimeout(() => { overlay.remove(); resolve(true); }, 300);
        };

        overlay.querySelector('.modal-cancel').onclick = () => {
            overlay.classList.remove('active');
            setTimeout(() => { overlay.remove(); resolve(false); }, 300);
        };
    });
}