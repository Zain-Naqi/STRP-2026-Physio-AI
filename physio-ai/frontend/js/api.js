/**
 * API Service Client
 * 
 * Handles HTTP connection, request headers, error handling,
 * and token management (localStorage).
 */

const API_BASE_URL = 'http://localhost:5000/api';

const ApiClient = {
  /**
   * Save auth token to localStorage
   */
  setToken(token) {
    localStorage.setItem('physioai_token', token);
  },

  /**
   * Retrieve auth token from localStorage
   */
  getToken() {
    return localStorage.getItem('physioai_token');
  },

  /**
   * Remove token (Logout)
   */
  clearToken() {
    localStorage.removeItem('physioai_token');
  },

  /**
   * Generic request wrapper with content-type and authorization headers.
   */
  async request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    
    // Setup headers
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    const token = this.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const config = {
      ...options,
      headers,
    };

    try {
      const response = await fetch(url, config);
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.message || `Request failed with status ${response.status}`);
      }

      return data;
    } catch (error) {
      // Catch connection errors or API custom errors
      console.error(`[API Error] ${endpoint}:`, error);
      
      // If it looks like a network connection failure
      if (error.message.includes('Failed to fetch')) {
        throw new Error('Could not connect to the authentication server. Please verify the backend service is running on port 5000.');
      }
      
      throw error;
    }
  },

  /**
   * Authenticate user credentials
   */
  async login(email, password) {
    const result = await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });

    if (result.success && result.token) {
      this.setToken(result.token);
    }
    return result;
  },

  /**
   * Register new user profile
   */
  async register(fullName, email, password, confirmPassword, role) {
    const result = await this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        full_name: fullName,
        email,
        password,
        confirmPassword,
        role,
      }),
    });

    if (result.success && result.token) {
      this.setToken(result.token);
    }
    return result;
  },

  /**
   * Verify session token and retrieve user summary
   */
  async checkSession() {
    if (!this.getToken()) return null;
    try {
      return await this.request('/auth/me', {
        method: 'GET',
      });
    } catch (error) {
      // Token is likely invalid or expired
      this.clearToken();
      return null;
    }
  }
};
