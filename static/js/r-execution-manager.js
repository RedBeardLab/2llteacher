/**
 * R Execution Manager for LLTeacher
 * Handles WebR initialization and R code execution in the browser
 */
class RExecutionManager {
    constructor() {
        this.webR = null;
        this.isInitialized = false;
        this.isInitializing = false;
        this.initializationPromise = null;
    }

    async initialize() {
        if (this.isInitialized) {
            return this.webR;
        }

        if (this.isInitializing) {
            return this.initializationPromise;
        }

        this.isInitializing = true;
        console.log('Initializing WebR...');

        this.initializationPromise = this._doInitialize();
        return this.initializationPromise;
    }

    async _doInitialize() {
        try {
            // Show global loading indicator
            this.showGlobalLoadingState(true);

            // Initialize WebR
            const { WebR } = await import('https://webr.r-wasm.org/latest/webr.mjs');
            this.webR = new WebR({
                SW_URL: 'https://webr.r-wasm.org/latest/',
            });

            await this.webR.init();

            // Set up webr::canvas as default graphics device for proper plot capture
            await this.webR.evalRVoid('options(device=webr::canvas)');

            // Install common packages
            await this.installCommonPackages();

            this.isInitialized = true;
            this.isInitializing = false;

            console.log('WebR initialized successfully');
            this.showGlobalLoadingState(false);
            this.enableAllRunButtons();

            return this.webR;
        } catch (error) {
            console.error('Failed to initialize WebR:', error);
            this.isInitializing = false;
            this.showGlobalLoadingState(false);
            this.showGlobalError('Failed to initialize R environment. Please refresh the page to try again.');
            throw error;
        }
    }

    async installCommonPackages() {
        try {
            // Install commonly used packages
            const packages = ['ggplot2', 'dplyr', 'tidyr'];
            for (const pkg of packages) {
                try {
                    await this.webR.evalR(`if (!require(${pkg}, quietly = TRUE)) { install.packages("${pkg}", quiet = TRUE) }`);
                } catch (e) {
                    console.warn(`Failed to install package ${pkg}:`, e);
                    // Continue with other packages
                }
            }
        } catch (error) {
            console.warn('Some packages failed to install:', error);
            // Don't throw - WebR is still usable without these packages
        }
    }

    async executeCode(code, outputContainer) {
        if (!this.isInitialized) {
            await this.initialize();
        }

        try {
            // Clear previous output
            outputContainer.innerHTML = '';
            this.showExecutionState(outputContainer, 'running');

            // Use WebR's proper captureR method for output and plot capture
            const shelter = await new this.webR.Shelter();
            const result = await shelter.captureR(code, { withAutoprint: true });

            // Process captured output
            let textOutput = '';
            let hasError = false;

            // Extract text output from captured results
            if (result.output && result.output.length > 0) {
                const outputLines = [];
                for (const item of result.output) {
                    if (item.type === 'stdout' || item.type === 'stderr') {
                        outputLines.push(item.data);
                    } else if (item.type === 'error') {
                        hasError = true;
                        // Extract error message from R error object
                        try {
                            const errorMsg = await item.data.toString();
                            outputLines.push(`Error: ${errorMsg}`);
                        } catch (e) {
                            outputLines.push('An error occurred during execution');
                        }
                    }
                }
                textOutput = outputLines.join('\n');
            }

            // If no output captured but we have a result, try to get the result value
            if (!textOutput.trim() && result.result && !hasError) {
                try {
                    const resultStr = await result.result.toString();
                    if (resultStr && resultStr.trim() && resultStr !== 'NULL') {
                        textOutput = resultStr;
                    }
                } catch (e) {
                    // Ignore conversion errors
                }
            }

            // Display results with captured plots
            this.displayResults(outputContainer, textOutput, result.images || [], hasError);

            // Clean up shelter
            shelter.purge();

        } catch (error) {
            console.error('R execution error:', error);
            this.showExecutionError(outputContainer, error.message || 'Failed to execute R code');
        }
    }

    displayResults(container, output, plots, hasError) {
        container.innerHTML = '';

        if (hasError) {
            container.innerHTML = `
                <div class="r-execution-result error">
                    <div class="r-error">
                        <i class="bi bi-exclamation-triangle"></i>
                        <strong>Error:</strong>
                        <pre><code>${this.escapeHtml(output)}</code></pre>
                    </div>
                </div>
            `;
        } else {
            let resultHtml = '<div class="r-execution-result success">';

            // Add text output if present
            if (output && output.trim()) {
                resultHtml += `
                    <div class="r-output">
                        <div class="r-output-header">
                            <i class="bi bi-terminal"></i>
                            <strong>Output:</strong>
                        </div>
                        <pre><code>${this.escapeHtml(output)}</code></pre>
                    </div>
                `;
            }

            // Add plots if present (ImageBitmap objects from WebR)
            if (plots && plots.length > 0) {
                resultHtml += `
                    <div class="r-plots">
                        <div class="r-output-header">
                            <i class="bi bi-graph-up"></i>
                            <strong>Plot:</strong>
                        </div>
                    </div>
                `;

                // We'll add the ImageBitmap plots after setting the HTML
                container.innerHTML = resultHtml + '</div>';

                // Now add the ImageBitmap plots as canvas elements
                const plotsContainer = container.querySelector('.r-plots');
                plots.forEach((imageBitmap, index) => {
                    const canvas = document.createElement('canvas');
                    canvas.width = imageBitmap.width;
                    canvas.height = imageBitmap.height;
                    canvas.className = 'r-plot';
                    canvas.style.maxWidth = '100%';
                    canvas.style.height = 'auto';

                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(imageBitmap, 0, 0);

                    plotsContainer.appendChild(canvas);
                });
                return; // Early return since we already set innerHTML
            }

            // Show success message if no output
            if (!output.trim() && plots.length === 0) {
                resultHtml += `
                    <div class="r-success">
                        <i class="bi bi-check-circle"></i>
                        <span>Code executed successfully (no output)</span>
                    </div>
                `;
            }

            resultHtml += '</div>';
            container.innerHTML = resultHtml;
        }
    }

    showExecutionState(container, state) {
        if (state === 'running') {
            container.innerHTML = `
                <div class="r-execution-state running">
                    <i class="bi bi-arrow-repeat spin"></i>
                    <span>Executing R code...</span>
                </div>
            `;
        }
    }

    showExecutionError(container, message) {
        container.innerHTML = `
            <div class="r-execution-result error">
                <div class="r-error">
                    <i class="bi bi-exclamation-triangle"></i>
                    <strong>Execution Error:</strong>
                    <pre><code>${this.escapeHtml(message)}</code></pre>
                </div>
            </div>
        `;
    }

    showGlobalLoadingState(show) {
        let indicator = document.getElementById('webr-loading-indicator');

        if (show && !indicator) {
            // Create a non-blocking toast notification instead of full-screen overlay
            indicator = document.createElement('div');
            indicator.id = 'webr-loading-indicator';
            indicator.className = 'toast show position-fixed top-0 end-0 m-3';
            indicator.style.zIndex = '1050';
            indicator.innerHTML = `
                <div class="toast-header">
                    <i class="bi bi-arrow-repeat spin text-primary me-2"></i>
                    <strong class="me-auto">R Environment</strong>
                </div>
                <div class="toast-body">
                    Initializing R environment in the background...
                </div>
            `;
            document.body.appendChild(indicator);
        } else if (!show && indicator) {
            // Fade out the toast
            indicator.classList.remove('show');
            setTimeout(() => {
                if (indicator.parentNode) {
                    indicator.remove();
                }
            }, 300);
        }
    }

    showGlobalError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger alert-dismissible fade show webr-global-error';
        errorDiv.innerHTML = `
            <i class="bi bi-exclamation-triangle"></i>
            <strong>R Environment Error:</strong> ${this.escapeHtml(message)}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        const container = document.querySelector('.container');
        if (container) {
            container.insertBefore(errorDiv, container.firstChild);
        }
    }

    enableAllRunButtons() {
        const buttons = document.querySelectorAll('.r-run-button');
        buttons.forEach(button => {
            button.disabled = false;
            button.innerHTML = '<i class="bi bi-play-fill"></i> Run Code';

            // Ensure click handler is bound for existing buttons
            const messageId = button.getAttribute('data-message-id');
            if (messageId && !button.hasAttribute('data-handler-bound')) {
                this.bindButtonClickHandler(button, messageId);
                button.setAttribute('data-handler-bound', 'true');
            }
        });
    }

    bindButtonClickHandler(button, messageId) {
        button.addEventListener('click', async () => {
            if (!this.isInitialized) {
                console.error('WebR not initialized yet');
                return;
            }

            // Get the R code from the message - try multiple selectors
            let codeElement = document.querySelector(`[data-message-id="${messageId}"] code.language-r`);
            if (!codeElement) {
                // Fallback: try without language-r class
                codeElement = document.querySelector(`[data-message-id="${messageId}"] .r-code-container code`);
            }
            if (!codeElement) {
                // Another fallback: try any code element in the message
                codeElement = document.querySelector(`[data-message-id="${messageId}"] pre code`);
            }

            if (!codeElement) {
                console.error('R code not found for message', messageId);
                console.log('Message container:', document.querySelector(`[data-message-id="${messageId}"]`));
                console.log('All message containers:', document.querySelectorAll('[data-message-id]'));
                console.log('All code elements:', document.querySelectorAll('code'));
                console.log('All r-code-containers:', document.querySelectorAll('.r-code-container'));
                return;
            }

            const code = codeElement.textContent;
            const outputContainer = document.getElementById(`r-output-${messageId}`);

            if (!outputContainer) {
                console.error('Output container not found for message', messageId);
                return;
            }

            // Execute the R code
            try {
                await this.executeCode(code, outputContainer);
            } catch (error) {
                console.error('Error executing R code:', error);
                outputContainer.innerHTML = `
                    <div class="r-execution-result error">
                        <div class="r-error">
                            <i class="bi bi-exclamation-triangle"></i>
                            <strong>Execution Error:</strong>
                            <pre><code>Failed to execute R code: ${error.message}</code></pre>
                        </div>
                    </div>
                `;
            }
        });
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Export for use in other modules
window.RExecutionManager = RExecutionManager;
