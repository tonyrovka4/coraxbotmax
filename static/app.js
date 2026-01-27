/**
 * Cloud Manager Application
 * Handles Max WebApp integration, Authentication, and Form management
 */
class CloudManagerApp {
    constructor() {
        // Initialize Max WebApp
        this.app = window.WebApp;

        // Check if running inside Max Messenger
        // initData is a string; if it's empty, we're just in a browser
        if (!this.app || !this.app.initData) {
            document.body.innerHTML = `
                <div style="display:flex;flex-direction:column;justify-content:center;align-items:center;height:100vh;text-align:center;padding:20px;">
                    <h1 style="margin-bottom:10px;">Доступ запрещен</h1>
                    <p>Пожалуйста, откройте это приложение через Max Messenger.</p>
                </div>
            `;
            throw new Error("Running outside Max Messenger");
        }

        // Store initData for API authentication
        this.initData = this.app.initData;

        // Create webapp reference for compatibility
        this.webapp = this.app;

        this.unknownStageLabel = 'unknown';

        // UI Elements
        this.menuSection = document.getElementById('menuSection');
        this.resourcesSection = document.getElementById('resourcesSection');
        this.serviceSelectionSection = document.getElementById('serviceSelectionSection');
        this.formSection = document.getElementById('formSection');
        this.deploymentSection = document.getElementById('deploymentSection');
        this.setupDeploymentActions();

        // Setup custom alert modal
        this.setupCustomAlert();

        // Initialize the application
        if (this.menuSection) {
            this.init();
        } else {
            // We might be on the login page (unauthenticated)
            this.authInit();
        }
    }

    /**
     * Create a mock Max WebApp object for testing outside Max
     */
    createMockWebApp() {
        return {
            expand: () => { },
            ready: () => { },
            sendData: (data) => console.log('WebApp sendData:', data),
            themeParams: {},
            openLink: (url) => window.open(url, '_blank'),
            close: () => window.close(),
            initData: ''
        };
    }

    /**
     * Setup custom alert modal functionality
     */
    setupCustomAlert() {
        this.alertModal = document.getElementById('customAlertModal');
        this.alertMessage = document.getElementById('alertMessage');
        this.alertIcon = document.getElementById('alertIcon');
        this.alertOkBtn = document.getElementById('alertOkBtn');
        this.alertOverlay = this.alertModal?.querySelector('.custom-alert-overlay');

        if (this.alertOkBtn) {
            this.alertOkBtn.addEventListener('click', () => this.hideAlert());
        }
        if (this.alertOverlay) {
            this.alertOverlay.addEventListener('click', () => this.hideAlert());
        }
        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.alertModal && !this.alertModal.classList.contains('hidden')) {
                this.hideAlert();
            }
        });
    }

    /**
     * Show custom alert modal
     * @param {string} message - The message to display
     * @param {string} type - Alert type: 'error', 'success', or 'info'
     */
    showAlert(message, type = 'error') {
        if (!this.alertModal || !this.alertMessage || !this.alertIcon) {
            // Fallback to native alert if modal not available
            alert(message);
            return;
        }

        this.alertMessage.textContent = message;

        // Reset icon classes
        this.alertIcon.className = 'custom-alert-icon';

        // Set icon and style based on type
        if (type === 'success') {
            this.alertIcon.textContent = '✓';
            this.alertIcon.classList.add('alert-icon-success');
        } else if (type === 'info') {
            this.alertIcon.textContent = 'ℹ';
            this.alertIcon.classList.add('alert-icon-info');
        } else {
            this.alertIcon.textContent = '!';
            // Default error style (no additional class needed)
        }

        this.alertModal.classList.remove('hidden');
        this.alertOkBtn?.focus();
    }

    /**
     * Hide custom alert modal
     */
    hideAlert() {
        if (this.alertModal) {
            this.alertModal.classList.add('hidden');
        }
    }

    /**
     * Main initialization sequence
     */
    /**
     * Main initialization sequence for authenticated users
     */
    init() {
        this.setupWebApp();
        this.setupTheme();
        this.setupNavigation();
        this.setupForm();
        this.setupInputAnimations();
        this.setupInputAnimations();
        this.setupCleanup();
        // Setup manual update handler
        this.setupVmManualUpdate();

        // Initial load (optional, as we load on section open)
        this.loadVmCount();
    }

    /**
     * Initialization for unauthenticated users (login page)
     */
    authInit() {
        this.setupWebApp();
        this.setupTheme();
        this.setupAuthButtons();
    }

    /**
     * Lazy load VM count from the server
     */
    async loadVmCount() {
        const vmCountElement = document.getElementById('vmCount');
        if (!vmCountElement) return;

        try {
            const response = await fetch('/api/vms-count', {
                headers: {
                    'X-Auth-Data': this.initData
                }
            });
            const data = await response.json();

            if (data.success) {
                vmCountElement.textContent = data.count;
            } else {
                // Use textContent instead of innerHTML to prevent XSS
                vmCountElement.textContent = 'Ошибка загрузки';
                vmCountElement.classList.add('vm-error');
                console.error('Error loading VM count:', data.error);
            }
        } catch (error) {
            // Use textContent instead of innerHTML to prevent XSS
            vmCountElement.textContent = 'Сеть недоступна';
            vmCountElement.classList.add('vm-error');
            console.error('Network error loading VM count:', error);
        }
    }

    /**
     * Setup manual VM count update button
     */
    setupVmManualUpdate() {
        const refreshBtn = document.getElementById('refreshVmCountBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', async () => {
                const icon = refreshBtn.querySelector('.btn-icon');

                // Add spinning animation class to icon
                if (icon) icon.style.animation = 'spin 0.8s linear infinite';
                refreshBtn.disabled = true;

                await this.loadVmCount();

                // Stop animation and re-enable
                refreshBtn.disabled = false;
                if (icon) icon.style.animation = '';
            });
        }
    }

    /**
     * Start polling for VM count (every 15 seconds)
     */
    startVmCountPolling() {
        this.stopVmCountPolling(); // Clear existing to be safe

        this.loadVmCount(); // Immediate load

        // 15 seconds interval
        this.vmPollingInterval = setInterval(() => {
            this.loadVmCount();
        }, 15000);
    }

    /**
     * Stop polling for VM count
     */
    stopVmCountPolling() {
        if (this.vmPollingInterval) {
            clearInterval(this.vmPollingInterval);
            this.vmPollingInterval = null;
        }
    }

    /**
     * Configure Max WebApp environment
     */
    setupWebApp() {
        try {
            this.webapp.expand();
            this.webapp.ready();
        } catch (e) {
            console.log('Running outside Max WebApp environment');
        }
    }

    /**
     * Apply Max WebApp theme colors to CSS variables
     */
    setupTheme() {
        document.documentElement.style.setProperty(
            '--webapp-theme-link-color',
            this.webapp.themeParams?.link_color || '#4a6cf7'
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
                    this.showAlert(`Ошибка подключения к ${provider}: ${error.message}`);
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
                this.showAlert('Успешная инициализация, но URL для перехода не получен', 'info');
            }
        } else {
            // Revert state and show error
            this.setButtonLoading(btn, false);
            const errorMsg = data.error || 'Ошибка инициализации';
            this.showAlert(errorMsg);
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
            this.startVmCountPolling();
        });

        // Create Resource Button
        document.querySelector('[data-action="create"]')?.addEventListener('click', () => {
            this.switchPage(this.serviceSelectionSection);
            this.stopVmCountPolling();
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
                this.stopVmCountPolling();
            });
        });

        // 3. Back Buttons Handlers
        // Back to Menu (from Resources or Services)
        document.querySelectorAll('.back-to-menu-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.switchPage(this.menuSection);
                this.stopVmCountPolling();
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
     * Обработчик действий на экране деплоя
     */
    setupDeploymentActions() {
        const hideBtn = document.getElementById('hideDeployBtn');
        if (hideBtn) {
            hideBtn.addEventListener('click', () => {
                // Останавливаем активный опрос, чтобы не грузить сеть
                this.stopStatusPolling();

                // Показываем уведомление
                this.showAlert('Деплой продолжается в фоне. Проверьте раздел "Ресурсы" позже.', 'info');

                // Возвращаемся в меню
                this.switchPage(this.menuSection);
            });
        }
    }

    /**
     * Validate and process form data
     */
    async handleFormSubmit() {
        const titleInput = document.querySelector('.title-inp');
        const descInput = document.querySelector('.desc-inp');
        const subnetSelect = document.querySelector('.subnet-select');
        const flavorSelect = document.querySelector('.flavor-select');
        const choiceInput = document.querySelector('.choice-hidden');
        const cloudProjectIdInput = document.querySelector('.cloud-project-id-hidden');
        const submitBtn = document.querySelector('.s-btn');

        if (!titleInput || !subnetSelect || !flavorSelect) return;

        const title = titleInput.value.trim();
        const description = descInput ? descInput.value.trim() : '';
        const subnet = subnetSelect.value;
        const flavor = flavorSelect.value;
        const choice = choiceInput ? (choiceInput.value || "Не выбрано") : "Не выбрано";
        const cloudProjectId = cloudProjectIdInput ? cloudProjectIdInput.value : '';

        if (!subnet || !flavor) {
            this.showAlert("Пожалуйста, выберите подсеть и конфигурацию");
            return;
        }
        if (!title) {
            this.showAlert("Введите название виртуальной машины");
            return;
        }

        const data = { choice, title, desc: description, subnet, flavor, cloud_project_id: cloudProjectId };

        if (submitBtn) this.setButtonLoading(submitBtn, true);

        try {
            // 1. ИНИЦИАЛИЗАЦИЯ UI ДЕПЛОЯ (МЕТАМОРФОЗА)
            // Перед отправкой запроса подготовим экран
            const deployTitle = document.getElementById('deployTitle');
            const deploySubtitle = document.getElementById('deploySubtitle');
            const terminalText = document.getElementById('terminalText');
            const heroBar = document.getElementById('heroProgressBar');
            const timeline = document.getElementById('deployTimeline');
            const hideBtn = document.getElementById('hideDeployBtn');

            if (deployTitle) deployTitle.textContent = `Запуск ${title}...`;
            if (deploySubtitle) deploySubtitle.textContent = `Конфигурация: ${flavor}`;
            if (terminalText) terminalText.textContent = "Sending request to control plane...";
            if (heroBar) heroBar.style.width = '5%'; // Начальный прогресс
            if (timeline) timeline.innerHTML = ''; // Очистка старых этапов

            // Сбрасываем кнопку "Свернуть" в дефолтное состояние
            if (hideBtn) {
                hideBtn.innerHTML = '<span class="btn-icon">×</span> Свернуть в фон';
                hideBtn.onclick = null; // Сброс старых обработчиков если были
                this.setupDeploymentActions(); // Перепривязка
            }

            // Переключаем страницу ПЕРЕД получением ответа для мгновенной реакции
            // (или можно после, если хотите показать ошибку на форме)

            const response = await fetch('/api/create-cluster', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Auth-Data': this.initData
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.success) {
                // Переход на экран деплоя (если еще не перешли)
                this.switchPage(this.deploymentSection);

                // Запуск поллинга с новым UI
                this.startStatusPolling(result.project_id, result.pipeline_id);
            } else {
                this.showAlert(result.error || 'Ошибка создания кластера');
            }
        } catch (error) {
            console.error('Error creating cluster:', error);
            this.showAlert(`Ошибка подключения: ${error.message}`);
        } finally {
            if (submitBtn) this.setButtonLoading(submitBtn, false);
        }
    }

    /**
     * Show the status section with initial message
     * Uses safe DOM manipulation to prevent XSS
     */
    showStatusSection(message) {
        let statusSection = document.getElementById('statusSection');

        if (!statusSection) {
            // Create status section structure safely using DOM APIs
            statusSection = document.createElement('div');
            statusSection.id = 'statusSection';
            statusSection.className = 'status-section';

            const statusContent = document.createElement('div');
            statusContent.className = 'status-content';

            // Spinner
            const spinnerDiv = document.createElement('div');
            spinnerDiv.className = 'status-spinner';
            const spinnerSpan = document.createElement('span');
            spinnerSpan.className = 'spinner';
            spinnerDiv.appendChild(spinnerSpan);

            // Status text
            const statusText = document.createElement('div');
            statusText.id = 'statusText';
            statusText.className = 'status-text';
            statusText.textContent = message;

            // Stage status
            const stageStatus = document.createElement('div');
            stageStatus.id = 'stageStatus';
            stageStatus.className = 'stage-status hidden';

            // Progress container
            const progressContainer = document.createElement('div');
            progressContainer.className = 'progress-container';
            const progressBar = document.createElement('div');
            progressBar.className = 'progress-bar';
            progressBar.id = 'progressBar';
            progressContainer.appendChild(progressBar);

            // Stage progress
            const stageProgress = document.createElement('div');
            stageProgress.id = 'stageProgress';
            stageProgress.className = 'stage-progress hidden';

            // Status links
            const statusLinks = document.createElement('div');
            statusLinks.id = 'statusLinks';
            statusLinks.className = 'status-links';

            // Assemble the structure
            statusContent.appendChild(spinnerDiv);
            statusContent.appendChild(statusText);
            statusContent.appendChild(stageStatus);
            statusContent.appendChild(progressContainer);
            statusContent.appendChild(stageProgress);
            statusContent.appendChild(statusLinks);
            statusSection.appendChild(statusContent);

            const formSection = document.getElementById('formSection');
            if (formSection) {
                formSection.appendChild(statusSection);
            }
        } else {
            statusSection.classList.remove('hidden');
            document.getElementById('statusText').textContent = message;
            const stageStatus = document.getElementById('stageStatus');
            if (stageStatus) stageStatus.classList.add('hidden');
            const stageProgress = document.getElementById('stageProgress');
            if (stageProgress) stageProgress.classList.add('hidden');
        }
    }

    /**
     * Update status section with pipeline info and links
     * Uses safe DOM manipulation instead of innerHTML to prevent XSS
     */
    updateStatusSection(message, pipelineUrl, projectUrl) {
        const statusText = document.getElementById('statusText');
        const statusLinks = document.getElementById('statusLinks');

        if (statusText) {
            statusText.textContent = message;
        }

        if (statusLinks) {
            // Clear existing content safely
            statusLinks.replaceChildren();

            // Create pipeline link safely using DOM APIs
            const pipelineLink = document.createElement('a');
            pipelineLink.href = pipelineUrl;
            pipelineLink.target = '_blank';
            pipelineLink.className = 'status-link';
            pipelineLink.textContent = 'Открыть Pipeline';

            // Create project link safely using DOM APIs
            const projectLink = document.createElement('a');
            projectLink.href = projectUrl;
            projectLink.target = '_blank';
            projectLink.className = 'status-link';
            projectLink.textContent = 'Открыть проект';

            statusLinks.appendChild(pipelineLink);
            statusLinks.appendChild(projectLink);
        }
    }

    /**
     * Show error in status section
     */
    showStatusError(errorMessage) {
        const statusSection = document.getElementById('statusSection');
        if (statusSection) {
            const spinner = statusSection.querySelector('.status-spinner');
            if (spinner) spinner.classList.add('hidden');

            const statusText = document.getElementById('statusText');
            if (statusText) {
                statusText.textContent = `❌ ${errorMessage}`;
                statusText.classList.add('status-error');
            }
        } else {
            this.showAlert(errorMessage);
        }
    }

    /**
     * Start polling for pipeline status updates
     */
    startStatusPolling(projectId, pipelineId) {
        // UI Элементы
        const heroBar = document.getElementById('heroProgressBar');
        const terminalText = document.getElementById('terminalText');
        const timeline = document.getElementById('deployTimeline');
        const deployIcon = document.getElementById('deployIcon');
        const pulseRing = document.querySelector('.pulse-ring');
        const hideBtn = document.getElementById('hideDeployBtn');

        if (this.statusPollingInterval) clearInterval(this.statusPollingInterval);

        // Включаем пульсацию
        if (pulseRing) pulseRing.style.display = 'block';

        let errorCount = 0;
        let pollInterval = 4000;

        const poll = async () => {
            try {
                const res = await fetch(`/api/pipeline-status/${projectId}/${pipelineId}`, {
                    headers: { 'X-Auth-Data': this.initData }
                });
                const data = await res.json();

                if (data.success) {
                    errorCount = 0;

                    // 1. Обновляем Hero Progress
                    if (heroBar) {
                        // Минимум 5%, чтобы было видно
                        const p = Math.max(data.percent || 0, 5);
                        heroBar.style.width = `${p}%`;
                    }

                    // 2. Обновляем Терминал
                    if (terminalText) {
                        if (data.status === 'success') {
                            terminalText.textContent = "Process completed successfully.";
                            terminalText.style.color = '#34C759';
                        } else if (data.status === 'failed') {
                            terminalText.textContent = "Critical Error. Process aborted.";
                            terminalText.style.color = '#FF3B30';
                        } else {
                            // Показываем текущий активный этап или статус
                            const activeStage = data.running_stage || data.status;
                            terminalText.textContent = `Executing: ${activeStage}...`;
                            terminalText.style.color = '#27C93F';
                        }
                    }

                    // 3. Обновляем Таймлайн (Умное обновление без перерисовки)
                    if (timeline && Array.isArray(data.stages)) {

                        // ВАЖНО: Мы НЕ делаем timeline.innerHTML = ''; 

                        data.stages.forEach((stage, index) => {
                            const isRunning = stage.status === 'running';
                            const isCompleted = ['success', 'completed'].includes(stage.status);

                            // Формируем правильный набор классов
                            let targetClass = 'timeline-item';
                            if (isRunning) targetClass += ' active';
                            if (isCompleted) targetClass += ' completed';

                            // Пытаемся найти уже существующий элемент по индексу
                            let existingItem = timeline.children[index];

                            if (existingItem) {
                                // ВАРИАНТ А: Элемент уже есть -> Обновляем только то, что изменилось

                                // 1. Обновляем классы (цвета точек)
                                if (existingItem.className !== targetClass) {
                                    existingItem.className = targetClass;
                                }

                                // 2. Обновляем проценты (текст)
                                const percentEl = existingItem.querySelector('.timeline-percent');
                                if (percentEl) {
                                    percentEl.textContent = `${stage.percent}%`;
                                }

                            } else {
                                // ВАРИАНТ Б: Элемента нет -> Создаем новый (только он сыграет анимацию)
                                const html = `
                                    <div class="${targetClass}">
                                        <div class="timeline-dot"></div>
                                        <div class="timeline-row">
                                            <span class="timeline-name">${stage.name || 'Unknown step'}</span>
                                            <span class="timeline-percent">${stage.percent}%</span>
                                        </div>
                                    </div>
                                `;
                                timeline.insertAdjacentHTML('beforeend', html);
                            }
                        });
                    }

                    // 4. Финишная прямая
                    if (['success', 'failed', 'canceled'].includes(data.status)) {
                        this.stopStatusPolling();

                        // Выключаем пульсацию
                        if (pulseRing) pulseRing.style.display = 'none';

                        if (data.status === 'success') {
                            if (deployIcon) deployIcon.textContent = '✅';
                            if (heroBar) heroBar.style.background = '#34C759'; // Зеленый

                            // Меняем кнопку "Свернуть" на "Готово"
                            if (hideBtn) {
                                hideBtn.className = 'btn btn-primary'; // Делаем главной кнопкой
                                hideBtn.innerHTML = '<span class="btn-icon">→</span> Перейти к ресурсам';
                                // Переопределяем поведение
                                hideBtn.replaceWith(hideBtn.cloneNode(true)); // Сброс листенеров
                                document.getElementById('hideDeployBtn').addEventListener('click', () => {
                                    this.switchPage(this.resourcesSection);
                                    this.startVmCountPolling();
                                });
                            }
                        } else {
                            if (deployIcon) deployIcon.textContent = '❌';
                            if (heroBar) heroBar.style.background = '#FF3B30'; // Красный
                        }
                        return;
                    }
                }
            } catch (error) {
                console.error('Polling error', error);
                errorCount++;
                if (errorCount > 5) this.stopStatusPolling();
            }
            this.statusPollingTimeout = setTimeout(poll, pollInterval);
        };

        poll();
    }

    /**
     * Stop polling for pipeline status
     */
    stopStatusPolling() {
        if (this.statusPollingInterval) {
            clearInterval(this.statusPollingInterval);
            this.statusPollingInterval = null;
        }
        if (this.statusPollingTimeout) {
            clearTimeout(this.statusPollingTimeout);
            this.statusPollingTimeout = null;
        }
    }

    /**
     * Setup cleanup handlers for page unload
     */
    setupCleanup() {
        window.addEventListener('beforeunload', () => {
            this.stopStatusPolling();
            this.stopVmCountPolling();
        });
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
