# 🚀 AI-Powered Pull Request Reviewer (HackHazards 2026)

An automated, enterprise-grade CI/CD pipeline tool that acts as a Senior Staff Software Engineer. It listens to GitHub repositories 24/7 and automatically audits Pull Requests for bugs, security vulnerabilities, and performance issues using Google's Gemini 2.5 Flash AI.

## ✨ Features
* **Real-Time Webhook Integration:** Instantly detects when a new Pull Request is opened or synchronized.
* **Cryptographic Security:** Uses HMAC SHA-256 to verify GitHub Webhook signatures, ensuring only authorized payloads are processed.
* **Intelligent AI Analysis:** Prompts Gemini 2.5 Flash to act as a strict security auditor, utilizing official GitHub Markdown alerts (`[!CAUTION]`, `[!IMPORTANT]`) for a professional UI.
* **🤖 GitHub Auto-Commenter:** Uses GitHub API Personal Access Tokens to automatically post the full AI code review directly into the Pull Request conversation within seconds.
* **🏷️ Smart Auto-Labeling:** Dynamically tags the Pull Request with `🤖 AI Reviewed` and instantly flags critical code with `🚨 Security Risk` if vulnerabilities are detected.

## 🛠️ Tech Stack
* **Backend:** Node.js, Express.js
* **AI Model:** Google Generative AI (Gemini 2.5 Flash)
* **Networking:** Ngrok (Secure tunneling)
* **Security & Integration:** Node `crypto` library, GitHub REST API v3

## ⚙️ How to Run Locally

**1. Clone the repository and install dependencies:**
\`\`\`bash
npm install express dotenv @google/generative-ai
\`\`\`

**2. Configure your Environment Variables:**
Create a `.env` file in the root directory and add your secret keys:
\`\`\`text
GEMINI_API_KEY=your_gemini_key_here
GITHUB_WEBHOOK_SECRET=your_custom_secret_password
GITHUB_TOKEN=ghp_your_github_personal_access_token
\`\`\`

**3. Start the Server & Tunnel:**
Open two terminals side-by-side:
* **Terminal 1 (The Server):** \`node index.js\`
* **Terminal 2 (The Tunnel):** \`npx ngrok http 3000\`

**4. Configure GitHub Webhooks:**
* Go to your Repository **Settings** -> **Webhooks**. 
* Add your Ngrok URL and append `/analyze-pr` to the end.
* Set Content-Type to `application/json`.
* Paste your Webhook Secret.
* Select only **Pull Request** events and click Save.

## 🔒 Security Focus
This tool is designed to act as a first line of defense. It actively prevents hardcoded secrets, brute-force vulnerabilities, and performance-killing synchronous loops from ever reaching the main production branch.