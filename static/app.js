/**
 * Cloud Manager Application
 * Handles Telegram WebApp integration, Authentication, and Form management
 */
class CloudManagerApp {
    constructor() {
        // Initialize Telegram WebApp or fallback
        this.tg = window.Telegram?.WebApp || this.createMockTelegram();

        // UI Elements
        this.menuSection = document.getElementById('menuSection');
        this.resourcesSection = document.getElementById('resourcesSection');
        this.serviceSelectionSection = document.getElementById('serviceSelectionSection');
        this.formSection = document.getElementById('formSection');

        // Initialize the application
        if (this.menuSection) {
            this.init();
        } else {
            // We might be on the login page (unauthenticated)
            this.authInit();
        }
    }

    /**
     * Create a mock Telegram WebApp object for testing outside Telegram
     */
    createMockTelegram() {
        return {
            expand: () => { },
            ready: () => { },
            showAlert: (msg) => alert(msg),
            sendData: (data) => console.log('Telegram sendData:', data),
            themeParams: {},
            openLink: (url) => window.open(url, '_blank')
        };
    }

    /**
     * Main initialization sequence
     */
    /**
     * Main initialization sequence for authenticated users
     */
    init() {
        this.setupTelegram();
        this.setupTheme();
        this.setupNavigation();
        this.setupForm();
        this.setupInputAnimations();
    }

    /**
     * Initialization for unauthenticated users (login page)
     */
    authInit() {
        this.setupTelegram();
        this.setupTheme();
        this.setupAuthButtons();
    }

    /**
     * Configure Telegram WebApp environment
     */
    setupTelegram() {
        try {
            this.tg.expand();
            this.tg.ready();
        } catch (e) {
            console.log('Running outside Telegram environment');
        }
    }

    /**
     * Apply Telegram theme colors to CSS variables
     */
    setupTheme() {
        document.documentElement.style.setProperty(
            '--tg-theme-link-color',
            this.tg.themeParams?.link_color || '#4a6cf7'
        );
    }

    /**
     * Manage button loading state with spinner
     * @param {HTMLElement} btn - The button element
     * @param {boolean} isLoading - Whether to show loading state
     */
    setButtonLoading(btn, isLoading) {
        if (isLoading) {
            // Save original content if not already saved
            if (!btn.dataset.originalContent) {
                btn.dataset.originalContent = btn.innerHTML;
            }
            btn.disabled = true;
            // Add spinner and loading text
            btn.innerHTML = '<span class="spinner"></span> Загрузка...';
        } else {
            btn.disabled = false;
            // Restore original content
            if (btn.dataset.originalContent) {
                btn.innerHTML = btn.dataset.originalContent;
            }
        }
    }

    /**
     * Setup consolidated authentication button handlers
     * Uses data attributes to determine provider and endpoint
     */
    setupAuthButtons() {
        const authButtons = document.querySelectorAll('.js-auth-btn');

        authButtons.forEach(btn => {
            btn.addEventListener('click', async () => {
                const provider = btn.dataset.provider;
                const url = btn.dataset.url;

                console.log(`${provider} Auth button clicked`);
                this.setButtonLoading(btn, true);

                try {
                    const response = await fetch(url, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });

                    const data = await response.json();
                    this.handleAuthResponse(data, btn, provider);

                } catch (error) {
                    console.error(`${provider} OAuth error:`, error);
                    this.setButtonLoading(btn, false);
                    this.tg.showAlert(`Ошибка подключения к ${provider}: ${error.message}`);
                }
            });
        });
    }

    /**
     * Handle the response from auth initialization endpoints
     */
    handleAuthResponse(data, btn, provider) {
        if (data.success) {
            // Check for redirect URL
            const redirectUrl = data.auth_url;

            if (redirectUrl) {
                console.log('Redirecting to:', redirectUrl);
                window.location.href = redirectUrl;
            } else {
                // Fallback or specific logical branches if needed
                this.setButtonLoading(btn, false);
                this.tg.showAlert('Успешная инициализация, но URL для перехода не получен');
            }
        } else {
            // Revert state and show error
            this.setButtonLoading(btn, false);
            const errorMsg = data.error || 'Ошибка инициализации';
            this.tg.showAlert(errorMsg);
        }
    }

    /**
     * Setup navigation between Main and Form sections
     */
    /**
     * Setup navigation between sections
     */
    setupNavigation() {
        // 1. Menu Section Handlers
        // Resources Button
        document.querySelector('[data-action="resources"]')?.addEventListener('click', () => {
            this.switchPage(this.resourcesSection);
        });

        // Create Resource Button
        document.querySelector('[data-action="create"]')?.addEventListener('click', () => {
            this.switchPage(this.serviceSelectionSection);
        });

        // 2. Service Selection Handlers (Pangolin/Corax)
        document.querySelectorAll('.choice-card[data-choice]').forEach(card => {
            card.addEventListener('click', () => {
                const choice = card.dataset.choice;
                const hiddenInput = document.querySelector('.choice-hidden');

                if (hiddenInput) {
                    hiddenInput.value = choice;
                }

                this.switchPage(this.formSection);
            });
        });

        // 3. Back Buttons Handlers
        // Back to Menu (from Resources or Services)
        document.querySelectorAll('.back-to-menu-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.switchPage(this.menuSection);
            });
        });

        // Back to Services (from Form)
        document.querySelector('.back-to-services-btn')?.addEventListener('click', () => {
            this.switchPage(this.serviceSelectionSection);
        });
    }

    /**
     * Switch visible page with transition effect
     */
    /**
     * Switch visible page with transition effect
     * @param {HTMLElement} targetSection - The section element to show
     */
    switchPage(targetSection) {
        // Find the currently active section
        const activeSection = document.querySelector('.page-transition.active');

        if (!activeSection || !targetSection || activeSection === targetSection) return;

        // Start transition out
        activeSection.classList.remove('active');

        setTimeout(() => {
            activeSection.classList.add('hidden');
            targetSection.classList.remove('hidden');

            // Update Header Title depending on section
            const headerTitle = document.getElementById('headerTitle');
            if (headerTitle) {
                if (targetSection === this.menuSection) headerTitle.textContent = 'Меню';
                else if (targetSection === this.serviceSelectionSection) headerTitle.textContent = 'Выберите сервис';
            }

            // Small delay to trigger transition in
            setTimeout(() => {
                targetSection.classList.add('active');
            }, 50);
        }, 300);
    }

    /**
     * Setup form submission
     */
    setupForm() {
        document.querySelector('.s-btn')?.addEventListener('click', () => {
            this.handleFormSubmit();
        });
    }

    /**
     * Validate and process form data
     */
    handleFormSubmit() {
        const titleInput = document.querySelector('.title-inp');
        const descInput = document.querySelector('.desc-inp');
        const subnetSelect = document.querySelector('.subnet-select');
        const flavorSelect = document.querySelector('.flavor-select');
        const choiceInput = document.querySelector('.choice-hidden');

        if (!titleInput || !subnetSelect || !flavorSelect) return;

        const title = titleInput.value.trim();
        const description = descInput ? descInput.value.trim() : '';
        const subnet = subnetSelect.value;
        const flavor = flavorSelect.value;
        const choice = choiceInput ? (choiceInput.value || "Не выбрано") : "Не выбрано";

        if (!subnet || !flavor) {
            this.tg.showAlert("Пожалуйста, выберите подсеть и конфигурацию");
            return;
        }

        if (!title) {
            this.tg.showAlert("Введите название виртуальной машины");
            return;
        }

        const data = { choice, title, desc: description, subnet, flavor };
        this.tg.sendData(JSON.stringify(data));

        // Show confirmation
        this.tg.showAlert(`Запрос на создание ВМ отправлен!\n\nСервис: ${choice}\nКонфигурация: ${flavor}\nПодсеть: ${subnet}`);
    }

    /**
     * Add focus effects to input fields
     */
    setupInputAnimations() {
        document.querySelectorAll('.input-field').forEach(input => {
            input.addEventListener('focus', () => {
                input.parentElement?.classList.add('focused');
            });
            input.addEventListener('blur', () => {
                if (!input.value) {
                    input.parentElement?.classList.remove('focused');
                }
            });
        });
    }
}

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
    new CloudManagerApp();
});
