/**
 * Authentication Coordinator
 * 
 * Orchestrates login and register form submissions, performs basic
 * field validation, handles credentials feedback, and manages session states.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Initialize UI interactive events
  UI.initRoleSelectors();
  UI.initDevConsole();

  // Check if session is already active on load
  checkActiveSession();

  // Login Form Submission
  UI.elements.loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    UI.hideAlert(UI.elements.loginAlert);

    const email = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPassword').value;
    const rememberMe = document.getElementById('loginRemember').checked;

    // Basic Validation
    if (!email || !password) {
      UI.showAlert(UI.elements.loginAlert, 'Please fill in all fields.', 'error');
      return;
    }

    try {
      UI.setLoading(UI.elements.loginBtn, true);

      // Perform auth API request
      const response = await ApiClient.login(email, password);

      if (response.success) {
        UI.showAlert(UI.elements.loginAlert, 'Login successful! Redirecting...', 'success');
        
        // Save "Remember Me" preference if checked (optional future implementation)
        if (rememberMe) {
          localStorage.setItem('physioai_remember_email', email);
        } else {
          localStorage.removeItem('physioai_remember_email');
        }

        // Show successful login interface state
        setTimeout(() => {
          showAuthenticatedState(response.user);
        }, 1200);

      } else {
        UI.showAlert(UI.elements.loginAlert, response.message || 'Authentication failed.', 'error');
      }
    } catch (error) {
      UI.showAlert(UI.elements.loginAlert, error.message, 'error');
    } finally {
      UI.setLoading(UI.elements.loginBtn, false);
    }
  });

  // Registration Form Submission
  UI.elements.registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    UI.hideAlert(UI.elements.registerAlert);

    const fullName = document.getElementById('regName').value.trim();
    const email = document.getElementById('regEmail').value.trim();
    const password = document.getElementById('regPassword').value;
    const confirmPassword = document.getElementById('regConfirmPassword').value;
    const role = UI.elements.roleInput.value;

    // Field Validation
    if (!fullName || !email || !password || !confirmPassword) {
      UI.showAlert(UI.elements.registerAlert, 'Please fill in all fields.', 'error');
      return;
    }

    if (password !== confirmPassword) {
      UI.showAlert(UI.elements.registerAlert, 'Passwords do not match.', 'error');
      return;
    }

    if (password.length < 6) {
      UI.showAlert(UI.elements.registerAlert, 'Password must be at least 6 characters.', 'error');
      return;
    }

    if (!role) {
      UI.showAlert(UI.elements.registerAlert, 'Please select a role.', 'error');
      return;
    }

    try {
      UI.setLoading(UI.elements.registerBtn, true);

      // Perform registration API request
      const response = await ApiClient.register(fullName, email, password, confirmPassword, role);

      if (response.success) {
        UI.showAlert(UI.elements.registerAlert, 'Account created! Logging in...', 'success');
        
        // Show successful login state
        setTimeout(() => {
          showAuthenticatedState(response.user);
        }, 1200);

      } else {
        UI.showAlert(UI.elements.registerAlert, response.message || 'Registration failed.', 'error');
      }
    } catch (error) {
      UI.showAlert(UI.elements.registerAlert, error.message, 'error');
    } finally {
      UI.setLoading(UI.elements.registerBtn, false);
    }
  });

  // Auto-fill remembered email if present
  const rememberedEmail = localStorage.getItem('physioai_remember_email');
  if (rememberedEmail) {
    document.getElementById('loginEmail').value = rememberedEmail;
    document.getElementById('loginRemember').checked = true;
  }
});

/**
 * Verify active token and update page state accordingly
 */
async function checkActiveSession() {
  const session = await ApiClient.checkSession();
  if (session && session.success) {
    // Session is valid, display session state
    showAuthenticatedState(session.user);
  }
}

/**
 * Renders a clean success view within the current bounds to verify active state
 * without creating any navigation or dashboard components.
 */
function showAuthenticatedState(user) {
  if (user.role === 'patient') {
    window.location.href = 'patient-home.html';
  } else if (user.role === 'physiotherapist') {
    window.location.href = 'therapist-home.html';
  } else {
    window.location.href = 'patient-home.html';
  }
}
