require('dotenv').config();
const express = require('express');
const crypto = require('crypto'); // Built-in Node module for cryptography
const { GoogleGenerativeAI } = require('@google/generative-ai');

const app = express();

// Capture the raw body so we can cryptographically verify the signature later
app.use(express.json({
    verify: (req, res, buf) => {
        req.rawBody = buf;
    }
}));

// 1. Validate API Keys & Secrets
if (!process.env.GEMINI_API_KEY) {
    console.error("❌ ERROR: GEMINI_API_KEY is missing in your .env file!");
    process.exit(1);
}
if (!process.env.GITHUB_WEBHOOK_SECRET) {
    console.error("❌ ERROR: GITHUB_WEBHOOK_SECRET is missing in your .env file!");
    process.exit(1);
}

// 2. Initialize Gemini 2.5 Flash
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash" });

// 3. Security Middleware: Verify GitHub Webhook Signature
function verifyGithubPayload(req, res, next) {
    const signature = req.headers['x-hub-signature-256'];
    if (!signature) {
        console.warn("⚠️ Unauthorized attempt: No signature found.");
        return res.status(401).json({ error: "Unauthorized: No signature found" });
    }

    const hmac = crypto.createHmac('sha256', process.env.GITHUB_WEBHOOK_SECRET);
    const digest = 'sha256=' + hmac.update(req.rawBody).digest('hex');

    if (crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(digest))) {
        next(); // Signature matches, proceed to the route
    } else {
        console.warn("⚠️ Unauthorized attempt: Signature mismatch.");
        return res.status(401).json({ error: "Unauthorized: Signature mismatch" });
    }
}

// 4. Webhook Endpoint for PR Analysis (Now protected by verifyGithubPayload)
app.post('/analyze-pr', verifyGithubPayload, async (req, res) => {
    try {
        // We expect the user (or GitHub) to send the code diff in the request body
        const { diff, pr_title, repo_name } = req.body;

        if (!diff) {
            return res.status(400).json({ error: "Missing 'diff' in request body." });
        }

        console.log(`[AI Reviewer] Analyzing PR for ${repo_name || 'Unknown Repo'}...`);

        // 5. The "Senior Engineer" Prompt
        const prompt = `
        You are an expert Senior Staff Software Engineer and Security Auditor.
        Your job is to review the following Pull Request code changes (Git Diff).

        Please provide a structured, professional code review with the following sections. Use Markdown formatting.
        1. 🐛 Bugs & Vulnerabilities (Identify any critical issues)
        2. ⚡ Performance Improvements (Suggest optimizations)
        3. 💡 Code Quality & Best Practices (Style, readability, maintainability)
        4. ✅ Overall Verdict (Approve, Request Changes, or Comment)

        Here is the PR information:
        Title: ${pr_title || 'Untitled PR'}
        Repository: ${repo_name || 'Unknown'}

        Git Diff:
        ${diff}
        `;

        // 6. Call Gemini to analyze the code
        const result = await model.generateContent(prompt);
        const reviewText = result.response.text();

        console.log("[AI Reviewer] ✅ Analysis complete!");

        // 7. Return the review
        res.json({
            status: "success",
            review: reviewText
        });

    } catch (error) {
        console.error("❌ Error during AI analysis:", error);
        res.status(500).json({ error: "Failed to analyze PR." });
    }
});

// 8. Start the Server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`=========================================`);
    console.log(`🚀 PR Reviewer AI running on port ${PORT}`);
    console.log(`=========================================`);
    console.log(`Waiting for secure code diffs at http://localhost:${PORT}/analyze-pr`);
});