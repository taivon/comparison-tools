/**
 * Address Autocomplete Component
 * Uses Google Places Autocomplete API via our backend proxy
 */

class AddressAutocomplete {
    constructor(inputElement, options = {}) {
        this.input = inputElement;
        this.options = {
            minChars: 3,
            debounceMs: 300,
            apiEndpoint: '/apartments/api/address-autocomplete/',
            detailsEndpoint: '/apartments/api/place-details/',
            onSelect: null,  // Callback when address is selected
            ...options
        };

        this.dropdown = null;
        this.sessionToken = this.generateSessionToken();
        this.debounceTimer = null;
        this.selectedIndex = -1;
        this.suggestions = [];

        // Hidden fields to store coordinates
        this.latInput = options.latInput || null;
        this.lngInput = options.lngInput || null;
        this.placeIdInput = options.placeIdInput || null;

        this.init();
    }

    generateSessionToken() {
        return 'session_' + Math.random().toString(36).substring(2, 15);
    }

    init() {
        // Create dropdown container
        this.createDropdown();

        // Add event listeners
        this.input.addEventListener('input', this.handleInput.bind(this));
        this.input.addEventListener('keydown', this.handleKeydown.bind(this));
        this.input.addEventListener('blur', this.handleBlur.bind(this));
        this.input.addEventListener('focus', this.handleFocus.bind(this));

        // Mark as initialized
        this.input.dataset.autocompleteInitialized = 'true';
    }

    createDropdown() {
        this.dropdown = document.createElement('div');
        this.dropdown.className = 'address-autocomplete-dropdown';
        this.dropdown.style.cssText = `
            position: absolute;
            z-index: 1000;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            max-height: 300px;
            overflow-y: auto;
            display: none;
            width: 100%;
            margin-top: 4px;
        `;

        // Position relative to input
        const wrapper = document.createElement('div');
        wrapper.style.position = 'relative';
        this.input.parentNode.insertBefore(wrapper, this.input);
        wrapper.appendChild(this.input);
        wrapper.appendChild(this.dropdown);
    }

    handleInput(e) {
        const query = e.target.value.trim();

        // Clear any existing timer
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        // Clear coordinates when user types (they need to select from dropdown)
        this.clearCoordinates();

        if (query.length < this.options.minChars) {
            this.hideDropdown();
            return;
        }

        // Debounce the API call
        this.debounceTimer = setTimeout(() => {
            this.fetchSuggestions(query);
        }, this.options.debounceMs);
    }

    handleKeydown(e) {
        if (!this.dropdown.style.display || this.dropdown.style.display === 'none') {
            return;
        }

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.selectedIndex = Math.min(this.selectedIndex + 1, this.suggestions.length - 1);
                this.updateSelection();
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.selectedIndex = Math.max(this.selectedIndex - 1, 0);
                this.updateSelection();
                break;
            case 'Enter':
                e.preventDefault();
                if (this.selectedIndex >= 0 && this.suggestions[this.selectedIndex]) {
                    this.selectSuggestion(this.suggestions[this.selectedIndex]);
                }
                break;
            case 'Escape':
                this.hideDropdown();
                break;
        }
    }

    handleBlur() {
        // Delay hiding to allow click on dropdown
        setTimeout(() => {
            this.hideDropdown();
        }, 200);
    }

    handleFocus() {
        if (this.suggestions.length > 0) {
            this.showDropdown();
        }
    }

    async fetchSuggestions(query) {
        try {
            const url = new URL(this.options.apiEndpoint, window.location.origin);
            url.searchParams.set('q', query);
            url.searchParams.set('session_token', this.sessionToken);

            const response = await fetch(url, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) {
                throw new Error('Failed to fetch suggestions');
            }

            const data = await response.json();
            this.suggestions = data.suggestions || [];
            this.renderSuggestions();
        } catch (error) {
            console.error('Autocomplete error:', error);
            this.hideDropdown();
        }
    }

    renderSuggestions() {
        if (this.suggestions.length === 0) {
            this.hideDropdown();
            return;
        }

        this.dropdown.innerHTML = '';
        this.selectedIndex = -1;

        this.suggestions.forEach((suggestion, index) => {
            const item = document.createElement('div');
            item.className = 'autocomplete-item';
            item.style.cssText = `
                padding: 12px 16px;
                cursor: pointer;
                border-bottom: 1px solid #f3f4f6;
                transition: background-color 0.15s;
            `;

            item.innerHTML = `
                <div style="font-weight: 500; color: #111827;">${this.escapeHtml(suggestion.main_text)}</div>
                <div style="font-size: 0.875rem; color: #6b7280; margin-top: 2px;">${this.escapeHtml(suggestion.secondary_text)}</div>
            `;

            item.addEventListener('mouseenter', () => {
                this.selectedIndex = index;
                this.updateSelection();
            });

            item.addEventListener('click', () => {
                this.selectSuggestion(suggestion);
            });

            this.dropdown.appendChild(item);
        });

        this.showDropdown();
    }

    updateSelection() {
        const items = this.dropdown.querySelectorAll('.autocomplete-item');
        items.forEach((item, index) => {
            if (index === this.selectedIndex) {
                item.style.backgroundColor = '#f3f4f6';
            } else {
                item.style.backgroundColor = 'white';
            }
        });
    }

    async selectSuggestion(suggestion) {
        // Update input with full address
        this.input.value = suggestion.description;

        // Fetch place details to get coordinates
        try {
            const url = new URL(this.options.detailsEndpoint, window.location.origin);
            url.searchParams.set('place_id', suggestion.place_id);
            url.searchParams.set('session_token', this.sessionToken);

            const response = await fetch(url, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (response.ok) {
                const details = await response.json();

                // Store coordinates in hidden fields if provided
                if (this.latInput) {
                    this.latInput.value = details.latitude;
                }
                if (this.lngInput) {
                    this.lngInput.value = details.longitude;
                }
                if (this.placeIdInput) {
                    this.placeIdInput.value = details.place_id;
                }

                // Store on input element data attributes
                this.input.dataset.latitude = details.latitude;
                this.input.dataset.longitude = details.longitude;
                this.input.dataset.placeId = details.place_id;
                this.input.dataset.formattedAddress = details.formatted_address;

                // Call onSelect callback if provided
                if (this.options.onSelect) {
                    this.options.onSelect(details);
                }
            }
        } catch (error) {
            console.error('Failed to fetch place details:', error);
        }

        // Generate new session token for next search
        this.sessionToken = this.generateSessionToken();

        this.hideDropdown();
    }

    clearCoordinates() {
        if (this.latInput) this.latInput.value = '';
        if (this.lngInput) this.lngInput.value = '';
        if (this.placeIdInput) this.placeIdInput.value = '';

        delete this.input.dataset.latitude;
        delete this.input.dataset.longitude;
        delete this.input.dataset.placeId;
    }

    showDropdown() {
        this.dropdown.style.display = 'block';
    }

    hideDropdown() {
        this.dropdown.style.display = 'none';
        this.selectedIndex = -1;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Helper function to find hidden fields for an address input
function findHiddenFieldsForInput(input) {
    const options = {};
    const form = input.closest('form');

    // Try to find hidden fields within the same form first
    if (form) {
        // Look for fields with name="google_latitude" etc.
        let latInput = form.querySelector('input[name="google_latitude"]');
        let lngInput = form.querySelector('input[name="google_longitude"]');
        let placeIdInput = form.querySelector('input[name="google_place_id"]');

        if (latInput) options.latInput = latInput;
        if (lngInput) options.lngInput = lngInput;
        if (placeIdInput) options.placeIdInput = placeIdInput;
    }

    // Fallback: try to find by standard IDs
    if (!options.latInput) {
        const latInput = document.getElementById('google_latitude');
        if (latInput) options.latInput = latInput;
    }
    if (!options.lngInput) {
        const lngInput = document.getElementById('google_longitude');
        if (lngInput) options.lngInput = lngInput;
    }
    if (!options.placeIdInput) {
        const placeIdInput = document.getElementById('google_place_id');
        if (placeIdInput) options.placeIdInput = placeIdInput;
    }

    return options;
}

// Auto-initialize on elements with data-address-autocomplete attribute
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-address-autocomplete]').forEach(input => {
        if (!input.dataset.autocompleteInitialized) {
            const options = findHiddenFieldsForInput(input);
            new AddressAutocomplete(input, options);
        }
    });
});

// Export for manual initialization
window.AddressAutocomplete = AddressAutocomplete;
