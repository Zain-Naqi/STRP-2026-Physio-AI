/**
 * Authentication Routes
 * 
 * Maps URL paths to controllers.
 */

const express = require('express');
const authController = require('../controllers/authController');

const router = express.Router();

// Public routes
router.post('/register', authController.register);
router.post('/login', authController.login);

// Session verification route
router.get('/me', authController.verifySession);

module.exports = router;
