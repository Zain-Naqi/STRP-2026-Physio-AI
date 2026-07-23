/**
 * UI Manipulation Service
 * 
 * Manages form slider transitions, alert feedback banners, input field highlights,
 * custom selectors (role cards), and developers utility console.
 */

const UI = {
  // Elements Cache
  elements: {
    sliderWrapper: document.getElementById('sliderWrapper'),
    loginForm: document.getElementById('loginForm'),
    registerForm: document.getElementById('registerForm'),
    
    // Alerts
    loginAlert: document.getElementById('loginAlert'),
    registerAlert: document.getElementById('registerAlert'),
    
    // Role Cards
    roleCards: document.querySelectorAll('.role-card'),
    roleInput: document.getElementById('regRole'),
    
    // Submit buttons
    loginBtn: document.getElementById('loginBtn'),
    registerBtn: document.getElementById('registerBtn'),
    
    // Dev Console credentials helper
    devCredentialPill: document.querySelector('.dev-credential-pill'),
    loginEmail: document.getElementById('loginEmail'),
    loginPassword: document.getElementById('loginPassword'),
  },

  /**
   * Switch the visible form (Login or Register) using a sliding transition.
   */
  switchToForm(formName) {
    this.hideAlert(this.elements.loginAlert);
    this.hideAlert(this.elements.registerAlert);

    if (formName === 'register') {
      this.elements.sliderWrapper.classList.add('show-register');
      // Update page title
      document.title = 'Create Account | PhysioAI';
    } else {
      this.elements.sliderWrapper.classList.remove('show-register');
      document.title = 'Sign In | PhysioAI';
    }
  },

  /**
   * Display alert feedback (success or error)
   */
  showAlert(alertEl, message, type = 'error') {
    if (!alertEl) return;
    
    // Reset classes
    alertEl.className = 'alert';
    
    // Set class type
    alertEl.classList.add(`alert-${type}`);
    
    // Set inner content with icon
    const icon = type === 'success' ? '✓' : '⚠️';
    alertEl.innerHTML = `<span class="alert-icon">${icon}</span> <span class="alert-message">${message}</span>`;
    
    // Add show trigger
    alertEl.classList.add('show');
  },

  /**
   * Dismiss alert feedback
   */
  hideAlert(alertEl) {
    if (!alertEl) return;
    alertEl.classList.remove('show');
  },

  /**
   * Set loading status on a primary button
   */
  setLoading(buttonEl, isLoading) {
    if (!buttonEl) return;
    
    if (isLoading) {
      buttonEl.classList.add('loading');
      buttonEl.setAttribute('disabled', 'true');
    } else {
      buttonEl.classList.remove('loading');
      buttonEl.removeAttribute('disabled');
    }
  },

  /**
   * Setup interactive click handlers for Role Selectors
   */
  initRoleSelectors() {
    this.elements.roleCards.forEach((card) => {
      card.addEventListener('click', () => {
        // Clear selected classes from all cards
        this.elements.roleCards.forEach((c) => c.classList.remove('selected'));
        
        // Mark current clicked card as selected
        card.classList.add('selected');
        
        // Find inside radio button and get value
        const radio = card.querySelector('input[type="radio"]');
        if (radio) {
          radio.checked = true;
          this.elements.roleInput.value = radio.value;
        }
      });
    });
  },

  /**
   * Setup helper developer console to autofill credentials for testing
   */
  initDevConsole() {
    if (this.elements.devCredentialPill) {
      this.elements.devCredentialPill.addEventListener('click', () => {
        // Autofill credentials
        this.elements.loginEmail.value = 'demo@physioai.com';
        this.elements.loginPassword.value = 'password123';
        
        // Focus the input to let the user see the visual change
        this.elements.loginEmail.focus();
        
        // Show subtle temporary success alert
        this.showAlert(this.elements.loginAlert, 'Demo credentials loaded! Click Sign In.', 'success');
        
        // Remove success banner after 4 seconds
        setTimeout(() => {
          this.hideAlert(this.elements.loginAlert);
        }, 4000);
      });
    }
  }
};

// Export UI helper globally
window.UI = UI;
