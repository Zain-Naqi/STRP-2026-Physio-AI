/**
 * Authentication Service
 * 
 * ARCHITECTURE NOTE:
 * Contains all authentication business logic, separated from
 * HTTP concerns (request/response handling).
 * 
 * This service is the single place to update when switching
 * from mock authentication to real database + bcrypt hashing.
 */

const jwt = require('jsonwebtoken');
const User = require('../models/User');

const JWT_SECRET = process.env.JWT_SECRET || 'physioai-dev-secret';
const JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || '7d';

/**
 * Generate a JWT token for an authenticated user.
 * @param {Object} user - User object (must have id, email, role)
 * @returns {string} Signed JWT
 */
function generateToken(user) {
  return jwt.sign(
    {
      id: user.id,
      email: user.email,
      role: user.role,
    },
    JWT_SECRET,
    { expiresIn: JWT_EXPIRES_IN }
  );
}

/**
 * Verify a password against the stored hash.
 * 
 * MOCK IMPLEMENTATION:
 * Currently uses a simple string comparison with a `$mock$` prefix.
 * 
 * FUTURE (MySQL + bcrypt):
 * ```
 * const bcrypt = require('bcryptjs');
 * return bcrypt.compare(plainPassword, hashedPassword);
 * ```
 */
async function verifyPassword(plainPassword, storedPassword) {
  const mockPrefix = '$mock$';
  if (storedPassword.startsWith(mockPrefix)) {
    return plainPassword === storedPassword.slice(mockPrefix.length);
  }
  return false;
}

/**
 * Hash a password for storage.
 * 
 * MOCK IMPLEMENTATION:
 * Stores with a `$mock$` prefix for identification.
 * 
 * FUTURE (bcrypt):
 * ```
 * const bcrypt = require('bcryptjs');
 * const salt = await bcrypt.genSalt(12);
 * return bcrypt.hash(plainPassword, salt);
 * ```
 */
async function hashPassword(plainPassword) {
  return `$mock$${plainPassword}`;
}

/**
 * Authenticate a user with email and password.
 * @param {string} email
 * @param {string} password
 * @returns {Object} { success, user, token, message }
 */
async function login(email, password) {
  const user = await User.findByEmail(email);

  if (!user) {
    return {
      success: false,
      message: 'No account found with this email address.',
    };
  }

  const isValid = await verifyPassword(password, user.password);

  if (!isValid) {
    return {
      success: false,
      message: 'Incorrect password. Please try again.',
    };
  }

  const token = generateToken(user);
  const { password: _, ...userWithoutPassword } = user;

  return {
    success: true,
    user: userWithoutPassword,
    token,
    message: 'Login successful.',
  };
}

/**
 * Register a new user account.
 * @param {Object} userData - { full_name, email, password, role }
 * @returns {Object} { success, user, token, message }
 */
async function register(userData) {
  const { full_name, email, password, role } = userData;

  const emailTaken = await User.emailExists(email);
  if (emailTaken) {
    return {
      success: false,
      message: 'An account with this email already exists.',
    };
  }

  const hashedPassword = await hashPassword(password);

  const newUser = await User.create({
    full_name,
    email,
    password: hashedPassword,
    role,
  });

  const token = generateToken(newUser);

  return {
    success: true,
    user: newUser,
    token,
    message: 'Account created successfully.',
  };
}

/**
 * Verify and decode a JWT token.
 * @param {string} token
 * @returns {Object|null} Decoded payload or null
 */
function verifyToken(token) {
  try {
    return jwt.verify(token, JWT_SECRET);
  } catch {
    return null;
  }
}

module.exports = {
  login,
  register,
  verifyToken,
  generateToken,
};
