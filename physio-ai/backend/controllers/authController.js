/**
 * Authentication Controller
 * 
 * Handles HTTP requests for login, registration, and session validation.
 * Delegates actual logic to the authService.
 */

const authService = require('../services/authService');

const authController = {
  /**
   * Handle POST /api/auth/register
   */
  async register(req, res) {
    try {
      const { full_name, email, password, confirmPassword, role } = req.body;

      // Validation
      if (!full_name || !email || !password || !confirmPassword || !role) {
        return res.status(400).json({
          success: false,
          message: 'All fields are required.',
        });
      }

      if (password !== confirmPassword) {
        return res.status(400).json({
          success: false,
          message: 'Passwords do not match.',
        });
      }

      if (password.length < 6) {
        return res.status(400).json({
          success: false,
          message: 'Password must be at least 6 characters long.',
        });
      }

      if (!['patient', 'physiotherapist'].includes(role)) {
        return res.status(400).json({
          success: false,
          message: 'Invalid role selection.',
        });
      }

      const result = await authService.register({
        full_name,
        email,
        password,
        role,
      });

      if (!result.success) {
        return res.status(400).json(result);
      }

      return res.status(201).json(result);
    } catch (error) {
      console.error('Registration controller error:', error);
      return res.status(500).json({
        success: false,
        message: 'An internal server error occurred during registration.',
      });
    }
  },

  /**
   * Handle POST /api/auth/login
   */
  async login(req, res) {
    try {
      const { email, password } = req.body;

      if (!email || !password) {
        return res.status(400).json({
          success: false,
          message: 'Email and password are required.',
        });
      }

      const result = await authService.login(email, password);

      if (!result.success) {
        return res.status(401).json(result);
      }

      return res.status(200).json(result);
    } catch (error) {
      console.error('Login controller error:', error);
      return res.status(500).json({
        success: false,
        message: 'An internal server error occurred during login.',
      });
    }
  },

  /**
   * Handle GET /api/auth/me (Verify session token)
   */
  async verifySession(req, res) {
    try {
      const authHeader = req.headers.authorization;
      if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return res.status(401).json({
          success: false,
          message: 'No authorization token provided.',
        });
      }

      const token = authHeader.split(' ')[1];
      const decoded = authService.verifyToken(token);

      if (!decoded) {
        return res.status(401).json({
          success: false,
          message: 'Invalid or expired token.',
        });
      }

      // In future, fetch the fresh user details from DB
      // const user = await User.findById(decoded.id);
      return res.status(200).json({
        success: true,
        user: {
          id: decoded.id,
          email: decoded.email,
          role: decoded.role,
        },
      });
    } catch (error) {
      console.error('Verify session controller error:', error);
      return res.status(500).json({
        success: false,
        message: 'An internal server error occurred verifying the session.',
      });
    }
  },
};

module.exports = authController;
