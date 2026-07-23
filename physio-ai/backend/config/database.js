/**
 * Database Configuration
 * 
 * ARCHITECTURE NOTE:
 * This module abstracts the database connection layer.
 * Currently returns a mock in-memory store.
 * 
 * To integrate MySQL later:
 * 1. Install mysql2: `npm install mysql2`
 * 2. Replace the mock pool with a real mysql2 pool/connection
 * 3. Update the query methods to use actual SQL
 * 4. The rest of the application (models, services) should
 *    require minimal changes due to this abstraction layer.
 */

const dbConfig = {
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT, 10) || 3306,
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || '',
  database: process.env.DB_NAME || 'physioai',
};

const mockDatabase = {
  users: [
    {
      id: '550e8400-e29b-41d4-a716-446655440000',
      full_name: 'Demo User',
      email: 'demo@physioai.com',
      password: '$mock$password123',
      role: 'patient',
      created_at: new Date('2025-01-01').toISOString(),
      updated_at: new Date('2025-01-01').toISOString(),
    },
  ],
};

function getDatabase() {
  return mockDatabase;
}

async function testConnection() {
  console.log('[Database] Using mock in-memory store');
  console.log('[Database] Config ready for MySQL:', {
    host: dbConfig.host,
    port: dbConfig.port,
    database: dbConfig.database,
  });
  return true;
}

module.exports = {
  dbConfig,
  getDatabase,
  testConnection,
};
