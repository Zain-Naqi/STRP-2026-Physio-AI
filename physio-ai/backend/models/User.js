/**
 * User Model
 * 
 * ARCHITECTURE NOTE:
 * This model encapsulates all user-related data access.
 * Currently operates on the in-memory mock database.
 * 
 * To integrate MySQL:
 * 1. Replace method implementations with SQL queries
 * 2. Keep the same method signatures
 * 3. Services that depend on this model won't need changes
 * 
 * Corresponding MySQL table schema:
 * ```sql
 * CREATE TABLE users (
 *   id          VARCHAR(36)  PRIMARY KEY,
 *   full_name   VARCHAR(255) NOT NULL,
 *   email       VARCHAR(255) NOT NULL UNIQUE,
 *   password    VARCHAR(255) NOT NULL,
 *   role        ENUM('patient', 'physiotherapist') NOT NULL DEFAULT 'patient',
 *   created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
 *   updated_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
 * );
 * ```
 */

const { v4: uuidv4 } = require('uuid');
const { getDatabase } = require('../config/database');

const User = {
  /**
   * Find a user by their email address.
   * @param {string} email
   * @returns {Object|null} User object or null
   */
  async findByEmail(email) {
    const db = getDatabase();
    const user = db.users.find(
      (u) => u.email.toLowerCase() === email.toLowerCase()
    );
    return user || null;
  },

  /**
   * Find a user by their unique ID.
   * @param {string} id
   * @returns {Object|null} User object or null
   */
  async findById(id) {
    const db = getDatabase();
    const user = db.users.find((u) => u.id === id);
    return user || null;
  },

  /**
   * Create a new user record.
   * @param {Object} userData - { full_name, email, password, role }
   * @returns {Object} Created user (without password)
   */
  async create(userData) {
    const db = getDatabase();
    const now = new Date().toISOString();

    const newUser = {
      id: uuidv4(),
      full_name: userData.full_name,
      email: userData.email.toLowerCase(),
      password: userData.password,
      role: userData.role || 'patient',
      created_at: now,
      updated_at: now,
    };

    db.users.push(newUser);

    const { password, ...userWithoutPassword } = newUser;
    return userWithoutPassword;
  },

  /**
   * Check if an email is already registered.
   * @param {string} email
   * @returns {boolean}
   */
  async emailExists(email) {
    const user = await this.findByEmail(email);
    return user !== null;
  },
};

module.exports = User;
