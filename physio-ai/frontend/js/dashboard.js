/**
 * Dashboard Shared Logic
 * 
 * Handles session verification, user data population, and logout
 * for both patient and physiotherapist home pages.
 */

document.addEventListener('DOMContentLoaded', async () => {
  // Verify session before rendering dashboard
  const session = await ApiClient.checkSession();
  
  if (!session || !session.success) {
    // If not authenticated, redirect back to login
    window.location.href = 'index.html';
    return;
  }

  const user = session.user;
  const isPatientPage = window.location.pathname.includes('patient-home.html') ||
    window.location.pathname.includes('exercise-library.html') ||
    window.location.pathname.includes('exercise-category.html');
  const isTherapistPage = window.location.pathname.includes('therapist-home.html');

  // Enforce role-based access
  if (isPatientPage && user.role !== 'patient') {
    window.location.href = 'therapist-home.html';
    return;
  }
  
  if (isTherapistPage && user.role !== 'physiotherapist') {
    window.location.href = 'patient-home.html';
    return;
  }

  // Populate UI with user data
  populateUserData(user);

  // Initialize logout functionality
  const logoutBtns = document.querySelectorAll('.logout-btn');
  logoutBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      ApiClient.clearToken();
      window.location.href = 'index.html';
    });
  });

  // Reveal body to prevent UI flicker
  document.body.classList.remove('preload');
});

/**
 * Populates DOM elements with user data based on specific class names.
 */
function populateUserData(user) {
  const firstName = user.full_name ? user.full_name.split(' ')[0] : 'User';
  
  document.querySelectorAll('.user-first-name').forEach(el => {
    el.textContent = firstName;
  });
  
  document.querySelectorAll('.user-full-name').forEach(el => {
    el.textContent = user.full_name || 'User';
  });
  
  document.querySelectorAll('.user-avatar-text').forEach(el => {
    el.textContent = firstName.charAt(0).toUpperCase();
  });
}
