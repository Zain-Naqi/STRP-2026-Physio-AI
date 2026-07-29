# PhysioAI — Premium Authentication Module

PhysioAI is a premium, AI-powered physiotherapy and movement assessment platform that uses computer vision to guide users through rehabilitation exercises. 

This repository contains the **Login and Registration pages** and their respective **modular backend foundation**, built to serve as a production-quality, database-ready authentication layer.

---

## 📁 Project Structure

The project maintains a strict separation between the frontend user interface and the backend business logic.

```text
physio-ai/
│
├── frontend/                  # Frontend User Interface
│   ├── assets/                # Visual branding illustrations
│   ├── css/
│   │   ├── main.css           # Typography, global variables, design system tokens
│   │   ├── components.css     # Form elements, buttons, role selectors, and alerts
│   │   └── auth.css           # Screen layout, grids, and sliding transitions
│   ├── js/
│   │   ├── api.js             # API request broker & token manager
│   │   ├── ui.js              # DOM interactions & transitions controller
│   │   └── auth.js            # Auth page logic & input validation coordinator
│   └── index.html             # High-fidelity SPA container
│
└── backend/                   # Backend Authentication Service
    ├── config/
    │   └── database.js        # Database connection pool and mock database
    ├── controllers/
    │   └── authController.js  # HTTP request parsers and input validators
    ├── models/
    │   └── User.js            # Database query abstractions (User table)
    ├── routes/
    │   └── authRoutes.js      # Endpoint route declarations
    ├── services/
    │   └── authService.js     # Passwords, JWT generation, and business rules
    ├── .env                   # Environment configurations
    ├── package.json           # Node.js dependencies configuration
    └── server.js              # Server bootstrapper & Express setup
```

---

## ⚙️ Backend Architecture & MySQL Migration Path

Although the application currently operates on a mock in-memory database to facilitate immediate, configuration-free testing, the codebase has been structured using a professional, tiered service architecture to support a local **MySQL database** (managed through DBeaver) later with minimal changes.

### Swapping Mock Storage for MySQL

1. **Install MySQL driver**:
   ```bash
   cd backend
   npm install mysql2
   ```

2. **Configure Environment (`backend/.env`)**:
   Uncomment and configure your local MySQL credentials:
   ```ini
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=root
   DB_PASSWORD=your_password
   DB_NAME=physioai
   ```

3. **Initialize MySQL Table**:
   Create the user table in your database matching the schema modeled in `backend/models/User.js`:
   ```sql
   CREATE TABLE users (
     id          VARCHAR(36)  PRIMARY KEY,
     full_name   VARCHAR(255) NOT NULL,
     email       VARCHAR(255) NOT NULL UNIQUE,
     password    VARCHAR(255) NOT NULL,
     role        ENUM('patient', 'physiotherapist') NOT NULL DEFAULT 'patient',
     created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
     updated_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
   );
   ```

4. **Update `backend/config/database.js`**:
   Replace the mock database object with a connection pool instance:
   ```javascript
   const mysql = require('mysql2/promise');
   const pool = mysql.createPool({
     host: process.env.DB_HOST,
     port: process.env.DB_PORT,
     user: process.env.DB_USER,
     password: process.env.DB_PASSWORD,
     database: process.env.DB_NAME,
     waitForConnections: true,
     connectionLimit: 10,
   });
   module.exports = { pool, testConnection: async () => pool.query('SELECT 1') };
   ```

5. **Update User Queries (`backend/models/User.js`)**:
   Change the Javascript array finders to SQL queries using the connection pool:
   ```javascript
   // Find by email example:
   async findByEmail(email) {
     const [rows] = await pool.query('SELECT * FROM users WHERE email = ?', [email]);
     return rows[0] || null;
   }
   ```

6. **Activate Password Hashing (`backend/services/authService.js`)**:
   Replace the mock hashing methods with real bcrypt algorithms:
   ```javascript
   const bcrypt = require('bcryptjs');
   
   async function verifyPassword(plainPassword, hashedPassword) {
     return bcrypt.compare(plainPassword, hashedPassword);
   }
   
   async function hashPassword(plainPassword) {
     const salt = await bcrypt.genSalt(12);
     return bcrypt.hash(plainPassword, salt);
   }
   ```

---

## 🎨 Visual Design & Style System

The user interface follows a modern, calm, human-centric wellness aesthetic using medical forest green tone highlights rather than generic sci-fi or neon gradients:

* **Primary Color Palette**: Deep Forest Green (`#1B3F36`), Serene Teal (`#3A8D7B`), and Soft Sage accents.
* **Layout Grid**: Large desktop screens feature a split-pane layout showing an abstract flowing rehab wave illustration on the left and the interactive auth form on the right. On tablet/mobile, the branding pane collapses gracefully to maximize screen usability.
* **Transitions**: Seamless page sliding animation wrapper allows switching from Login to Registration cards without page reloading.
* **Interactive Elements**:
  * Hover translation effects on primary controls.
  * Form highlight rings on focus (`#3A8D7B` border + `#E8F4F1` focus shadow).
  * Custom radio selectors styled as selectable cards for user role configuration.
  * Loading state spinners inside primary buttons.
* **Developer helper console**: Built-in developer helper pill at the bottom-right allows auto-filling pre-seeded mockup database account info (`demo@physioai.com` / `password123`) in one click.

---

## 🚀 Getting Started

### 1. Start the Backend API
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Install the server dependencies:
   ```bash
   npm install
   ```
3. Start the server in hot-reload watch mode:
   ```bash
   npm run dev
   ```
   The backend service will run on [http://localhost:5000](http://localhost:5000).

### 2. Start the Frontend Application
Since the frontend uses clean Vanilla CSS and JavaScript, you can open `frontend/index.html` directly in any web browser, or serve it using a lightweight local web server.

**Option A: Using Python Server (Recommended)**
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Start the server:
   ```bash
   python3 -m http.server 3000
   ```
3. Open your browser and navigate to [http://localhost:3000](http://localhost:3000).

**Option B: Using Node Serve**
1. Install serve globally:
   ```bash
   npm install -g serve
   ```
2. Launch server from root directory:
   ```bash
   serve frontend
   ```
3. Open your browser to the URL displayed.

### 3. Start the Exercise Service (Python)
The exercise recording/authoring and guided-playback pages (`record_exercise.html`, `perform_exercise.html`) talk to a separate FastAPI service that runs the MediaPipe pose-tracking pipeline. The browser owns the webcam; this service only receives frames over a WebSocket and returns annotated frames plus JSON status.

1. Navigate to the service directory:
   ```bash
   cd fullbody_RnM
   ```
2. (Recommended) create and activate a virtual environment, then install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the service in hot-reload mode:
   ```bash
   uvicorn server:app --reload --port 8000
   ```
   The service must be run from inside `fullbody_RnM/` so its relative `Models/` and `Exercises/` paths resolve correctly. It will be available at [http://localhost:8000](http://localhost:8000), with the frontend connecting to it over `ws://localhost:8000`.
