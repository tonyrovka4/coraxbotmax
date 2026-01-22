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
                    <h1 style="margin-bottom:10px;">⛔ Доступ запрещен</h1>
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
        this.setupCleanup();
        // Lazy load VM count after page load
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

        // Show loading state
        if (submitBtn) {
            this.setButtonLoading(submitBtn, true);
        }

        // Show status section
        this.showStatusSection('Создание проекта...');

        try {
            // Send request to backend API instead of using sendData
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
                // Update status with pipeline info
                this.updateStatusSection(
                    'Пайплайн запущен',
                    result.pipeline_url,
                    result.project_url
                );

                // Start polling for pipeline status
                this.startStatusPolling(result.project_id, result.pipeline_id);
            } else {
                this.showStatusError(result.error || 'Ошибка создания кластера');
            }
        } catch (error) {
            console.error('Error creating cluster:', error);
            this.showStatusError(`Ошибка подключения: ${error.message}`);
        } finally {
            if (submitBtn) {
                this.setButtonLoading(submitBtn, false);
            }
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
        const progressBar = document.getElementById('progressBar');
        const statusText = document.getElementById('statusText');
        const stageStatus = document.getElementById('stageStatus');
        const stageProgress = document.getElementById('stageProgress');
        
        // Clear any existing polling interval
        if (this.statusPollingInterval) {
            clearInterval(this.statusPollingInterval);
        }
        
        let errorCount = 0;
        const maxErrors = 3;
        let pollInterval = 5000; // Start with 5 seconds
        
        const poll = async () => {
            try {
                const res = await fetch(`/api/pipeline-status/${projectId}/${pipelineId}`, {
                    headers: {
                        'X-Auth-Data': this.initData
                    }
                });
                const data = await res.json();
                
                if (data.success) {
                    errorCount = 0; // Reset error count on success
                    
                    // Update progress bar
                    if (progressBar) {
                        progressBar.style.width = `${data.percent}%`;
                    }
                    
                    // Update status text
                    if (statusText) {
                        const statusMessages = {
                            'pending': 'Ожидание запуска...',
                            'running': `Выполнение... ${data.percent}%`,
                            'success': '✅ Пайплайн успешно завершен!',
                            'failed': '❌ Пайплайн завершился с ошибкой',
                            'canceled': '⚠️ Пайплайн отменен',
                            'skipped': '⏭️ Пайплайн пропущен',
                            'manual': '⏸️ Ожидание ручного запуска'
                        };
                        statusText.textContent = statusMessages[data.status] || `Статус: ${data.status}`;
                    }

                    if (stageStatus) {
                        if (data.running_stage) {
                            stageStatus.textContent = `Сейчас выполняется: ${data.running_stage}`;
                            stageStatus.classList.remove('hidden');
                        } else if (typeof data.total_stages === 'number' && data.total_stages > 0) {
                            stageStatus.textContent = `Готово этапов: ${data.completed_stages ?? 0} из ${data.total_stages}`;
                            stageStatus.classList.remove('hidden');
                        } else {
                            stageStatus.classList.add('hidden');
                        }
                    }

                    if (stageProgress) {
                        if (Array.isArray(data.stages) && data.stages.length) {
                            stageProgress.replaceChildren();
                            data.stages.forEach(stage => {
                                const safeStatus = ['pending', 'queued', 'running', 'completed', 'failed', 'canceled'].includes(stage.status)
                                    ? stage.status
                                    : 'pending';
                                const safePercent = Number.isFinite(stage.percent)
                                    ? Math.min(Math.max(stage.percent, 0), 100)
                                    : 0;
                                const stagePercent = `${safePercent}%`;
                                const stageName = stage.name || this.unknownStageLabel;

                                const stageRow = document.createElement('div');
                                stageRow.className = 'stage-row';

                                const stagePill = document.createElement('div');
                                stagePill.className = `stage-pill stage-${safeStatus}`;

                                const nameSpan = document.createElement('span');
                                nameSpan.textContent = stageName;

                                const percentSpan = document.createElement('span');
                                percentSpan.textContent = stagePercent;

                                stagePill.appendChild(nameSpan);
                                stagePill.appendChild(percentSpan);

                                const stageMeter = document.createElement('div');
                                stageMeter.className = 'stage-meter';

                                const meterFill = document.createElement('span');
                                meterFill.style.width = stagePercent;

                                stageMeter.appendChild(meterFill);
                                stageRow.appendChild(stagePill);
                                stageRow.appendChild(stageMeter);

                                stageProgress.appendChild(stageRow);
                            });
                            stageProgress.classList.remove('hidden');
                        } else {
                            stageProgress.classList.add('hidden');
                        }
                    }
                    
                    // Stop polling when pipeline is complete
                    if (['success', 'failed', 'canceled', 'skipped'].includes(data.status)) {
                        this.stopStatusPolling();
                        
                        // Hide spinner when complete
                        const spinner = document.querySelector('.status-spinner');
                        if (spinner) spinner.classList.add('hidden');
                        
                        // Update progress bar color on completion
                        if (progressBar) {
                            if (data.status === 'success') {
                                progressBar.classList.add('progress-success');
                            } else if (data.status === 'failed') {
                                progressBar.classList.add('progress-failed');
                            }
                        }
                        if (stageStatus && Array.isArray(data.stages)) {
                            const lastStage = data.stages.slice().reverse().find(stage => ['completed', 'failed', 'canceled'].includes(stage.status));
                            if (lastStage) {
                                stageStatus.textContent = `Готово! Последний этап: ${lastStage.name || this.unknownStageLabel}`;
                                stageStatus.classList.remove('hidden');
                            }
                        }
                        return;
                    }
                    
                    // Increase poll interval for long-running pipelines (max 30 seconds)
                    if (pollInterval < 30000) {
                        pollInterval = Math.min(pollInterval * 1.2, 30000);
                    }
                } else {
                    throw new Error(data.error || 'Unknown error');
                }
            } catch (error) {
                console.error('Error polling pipeline status:', error);
                errorCount++;
                
                if (errorCount >= maxErrors) {
                    this.stopStatusPolling();
                    if (statusText) {
                        statusText.textContent = '⚠️ Не удалось получить статус пайплайна';
                    }
                    return;
                }
            }
            
            // Schedule next poll
            this.statusPollingTimeout = setTimeout(poll, pollInterval);
        };
        
        // Start polling
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
