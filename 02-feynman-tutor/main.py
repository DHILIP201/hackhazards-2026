from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import google.generativeai as genai
from pypdf import PdfReader
from dotenv import load_dotenv
import os
import io
import webbrowser
import threading
import time
import json

# Load environment variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("WARNING: GEMINI_API_KEY not found in .env file!")

# Configure Gemini
genai.configure(api_key=api_key)

app = FastAPI(title="Feynman AI Tutor API")

# --- BACKEND MEMORY FOR MULTIPLE CHATS (PERSISTENT) ---
DB_FILE = "feynman_db.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_db():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(app_sessions, f, indent=4)

# This dictionary stores parsed PDFs and chat histories keyed by session_id
# It now loads from the local JSON file so it survives server restarts!
app_sessions = load_db()

# --- AUTO OPEN BROWSER LOGIC ---
def open_browser():
    time.sleep(1.5) # Wait for server to boot
    webbrowser.open("http://127.0.0.1:8000/")

@app.on_event("startup")
def startup_event():
    threading.Thread(target=open_browser).start()

# --- API MODELS ---
class ChatRequest(BaseModel):
    session_id: str
    user_message: str

# --- ENDPOINTS ---
@app.post("/upload-document/")
async def upload_document(session_id: str = Form(...), file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    try:
        contents = await file.read()
        pdf_reader = PdfReader(io.BytesIO(contents))
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        
        # Initialize or update the specific session's memory
        app_sessions[session_id] = {
            "document_text": text,
            "chat_history": []
        }
        
        # Save to database immediately
        save_db()
        
        return {"message": f"Successfully processed {file.filename}", "text_preview": text[:200]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading PDF: {str(e)}")

@app.post("/tutor-chat/")
async def tutor_chat(request: ChatRequest):
    session = app_sessions.get(request.session_id)
    
    if not session or not session.get("document_text"):
        raise HTTPException(status_code=400, detail="NO_DOCUMENT")
    
    user_message = request.user_message
    document = session["document_text"]
    history = session["chat_history"]
    
    # Append user message to history for the AI Context
    history.append({"role": "user", "parts": [user_message]})
    save_db()
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # UPGRADED EXAM-PREP PROMPT
        system_prompt = f"""
        You are an expert AI Tutor utilizing the Feynman Technique, specialized in helping students deeply understand concepts and score top marks in their exams. 
        Your goal is to test the user's understanding of the following source document.
        
        CRITICAL INSTRUCTIONS FOR INTERACTION:
        1. When a user asks for an explanation, gets stuck, or gives a wrong answer, provide a crystal clear, highly detailed, and interactive explanation. Use relatable analogies and break complex ideas into simple, digestible pieces.
        2. Do not just lecture them. After your detailed explanation, ALWAYS ask a thought-provoking follow-up question to test if they truly grasped what you just taught them.
        3. If they give a correct answer, evaluate it gently, praise them, and move to the next logical concept in the document.
        4. Match the detail and depth of advanced models, making sure the user feels fully prepared for an exam on this topic.
        
        Source Document:
        {document}
        
        At the very end of your response, you MUST include a mastery score based on how well the user currently understands the document.
        Format it exactly like this on a new line: [MASTERY: 25%]
        The score should go up as they answer correctly, and stay the same or drop if they are struggling. Start around 10%.
        """
        
        # Build messages for Gemini
        messages = [{"role": "user", "parts": [system_prompt]}]
        messages.extend(history)
        
        response = model.generate_content(messages)
        ai_response = response.text
        
        # Append AI response to history
        history.append({"role": "model", "parts": [ai_response]})
        session["chat_history"] = history
        save_db() # Save the new AI response to the database
        
        return {"response": ai_response}
        
    except Exception as e:
        # Remove the failed message from history
        history.pop()
        session["chat_history"] = history
        save_db()
        raise HTTPException(status_code=500, detail=f"AI Error: {str(e)}")


# --- GORGEOUS FRONTEND UI WITH AUTH & HISTORY ---
@app.get("/", response_class=HTMLResponse)
async def get_frontend():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Feynman AI Tutor</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            
            body { font-family: 'Inter', sans-serif; }
            .markdown-body p { margin-bottom: 0.75em; line-height: 1.6; }
            .markdown-body strong { color: #111827; font-weight: 600; }
            .markdown-body ul { list-style-type: disc; margin-left: 1.5em; margin-bottom: 0.75em; }
            .markdown-body code { background-color: #E5E7EB; padding: 0.2em 0.4em; border-radius: 0.25em; font-size: 0.875em; color: #DC2626; }
            
            /* Custom Scrollbar - Pushed to the very edge */
            ::-webkit-scrollbar { width: 8px; }
            ::-webkit-scrollbar-track { background: transparent; }
            ::-webkit-scrollbar-thumb { background: #D1D5DB; border-radius: 10px; }
            ::-webkit-scrollbar-thumb:hover { background: #9CA3AF; }

            .chat-item-active { background-color: #EEF2FF; border-left: 3px solid #4F46E5; }
            .chat-item { border-left: 3px solid transparent; transition: all 0.2s; }
            .chat-item:hover:not(.chat-item-active) { background-color: #F3F4F6; }
            
            /* To allow the 3 dots menu to show over other items */
            .menu-dropdown { box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); }
        </style>
    </head>
    <body class="h-screen flex bg-white text-gray-800 overflow-hidden font-sans relative">
        
        <!-- ==================== MAIN AUTHENTICATION OVERLAY ==================== -->
        <div id="auth-overlay" class="absolute inset-0 bg-gray-900/40 backdrop-blur-md z-40 flex items-center justify-center hidden">
            <div class="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-md border border-gray-100 transform transition-all">
                <div class="text-center mb-8">
                    <div class="w-12 h-12 bg-indigo-600 rounded-xl flex items-center justify-center text-white shadow-md mx-auto mb-4">
                        <i class="fa-solid fa-graduation-cap text-xl"></i>
                    </div>
                    <h2 class="text-2xl font-bold text-gray-900">Welcome to Feynman</h2>
                    <p class="text-gray-500 text-sm mt-1">Create an account or sign in to master your subjects.</p>
                </div>

                <div class="space-y-4">
                    <form onsubmit="handleEmailLogin(event)" class="space-y-5">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                            <input type="text" id="auth-name" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all" placeholder="e.g. Marie Curie">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
                            <input type="email" id="auth-email" required class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all" placeholder="you@university.edu">
                        </div>
                        <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-3 rounded-lg transition-colors shadow-md mt-2 flex justify-center items-center gap-2">
                            <span>Enter Feynman Tutor</span>
                            <i class="fa-solid fa-arrow-right text-sm"></i>
                        </button>
                    </form>
                </div>
            </div>
        </div>
        <!-- ============================================================================== -->

        <!-- Sidebar -->
        <aside class="w-64 bg-gray-50 border-r border-gray-200 flex flex-col flex-shrink-0 z-20">
            <!-- Sidebar Header -->
            <div class="p-5 pb-2">
                <div class="flex items-center gap-3 mb-6">
                    <div class="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-white shadow-sm shadow-indigo-200">
                        <i class="fa-solid fa-graduation-cap text-sm"></i>
                    </div>
                    <h1 class="font-bold text-lg text-gray-900 tracking-tight">Feynman Tutor</h1>
                </div>
                
                <button onclick="createNewChat()" class="w-full flex items-center gap-2 bg-white border border-gray-200 text-gray-700 px-4 py-2.5 rounded-lg hover:bg-gray-100 hover:text-indigo-600 shadow-sm text-sm font-semibold transition-all">
                    <i class="fa-solid fa-plus"></i> New chat
                </button>
            </div>
            
            <!-- History List -->
            <div class="flex-1 overflow-y-auto px-3 py-4">
                <p class="text-xs font-bold text-gray-400 mb-2 px-2 uppercase tracking-wider">Recent Chats</p>
                <ul id="history-list" class="space-y-1">
                    <!-- Chats injected via JS -->
                </ul>
            </div>
            
            <!-- User Profile (Populated via JS) -->
            <div id="user-profile-card" class="p-4 m-2 bg-white border border-gray-200 rounded-xl flex items-center justify-between shadow-sm group">
                <div class="flex items-center gap-3 overflow-hidden">
                    <div class="w-8 h-8 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center font-bold text-sm flex-shrink-0" id="user-avatar">
                        <!-- Initials -->
                    </div>
                    <div class="flex flex-col truncate">
                        <span class="text-sm font-semibold text-gray-800 truncate" id="user-name">Loading...</span>
                        <span class="text-xs text-gray-500 truncate" id="user-email">...</span>
                    </div>
                </div>
                <button onclick="signOut()" class="text-gray-400 hover:text-red-500 transition-colors p-1" title="Sign Out">
                    <i class="fa-solid fa-arrow-right-from-bracket"></i>
                </button>
            </div>
        </aside>

        <!-- Main Workspace -->
        <div class="flex-1 flex flex-col relative h-full w-full">
            
            <!-- Top Header (Mastery Tracker) -->
            <header class="h-16 border-b border-gray-100 px-6 flex items-center justify-between flex-shrink-0 bg-white z-10">
                <div class="flex items-center gap-3">
                    <i class="fa-solid fa-book-open text-gray-400"></i>
                    <span id="header-doc-title" class="font-semibold text-gray-700 truncate max-w-sm">New Chat</span>
                </div>
                <div class="flex items-center gap-4 bg-gray-50 px-4 py-2 rounded-lg border border-gray-100">
                    <span class="text-sm font-semibold text-gray-600">Topic Mastery</span>
                    <div class="w-48 h-2.5 bg-gray-200 rounded-full overflow-hidden">
                        <div id="mastery-bar" class="h-full bg-amber-500 rounded-full transition-all duration-1000 ease-out" style="width: 0%"></div>
                    </div>
                    <span id="mastery-text" class="text-sm font-bold text-amber-600">0%</span>
                </div>
            </header>

            <!-- Main Chat Scroll Wrapper (Full Width so scrollbar is at the right edge) -->
            <div id="chat-scroll-wrapper" class="flex-1 overflow-y-auto w-full">
                <!-- Inner Chat Container (Constrained width for readability) -->
                <main id="chat-container" class="flex flex-col gap-6 w-full max-w-4xl mx-auto p-6 pb-40">
                    <!-- Content injected via JS -->
                </main>
            </div>

            <!-- Input Area (Sticky Bottom with pointer-events-none so it doesn't block clicks on the text behind it) -->
            <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-white via-white to-transparent pt-10 pb-6 px-4 pointer-events-none">
                <div class="max-w-3xl mx-auto pointer-events-auto">
                    <div class="flex gap-2 mb-2 justify-end">
                        <button onclick="sendHintRequest()" class="text-xs bg-white border border-gray-200 text-gray-600 px-3 py-1.5 rounded-full hover:bg-gray-50 hover:text-indigo-600 transition-colors shadow-sm font-medium">
                            <i class="fa-regular fa-lightbulb text-amber-500 mr-1"></i> I'm stuck, give me a hint
                        </button>
                    </div>
                    
                    <div class="bg-white border border-gray-300 rounded-2xl shadow-lg p-2 flex items-end gap-2 focus-within:border-indigo-500 focus-within:ring-4 focus-within:ring-indigo-50 transition-all">
                        <button onclick="document.getElementById('file-upload').click()" class="p-2.5 text-gray-400 hover:text-indigo-600 transition-colors rounded-lg flex-shrink-0" title="Upload PDF">
                            <i class="fa-solid fa-paperclip text-lg"></i>
                        </button>
                        <input type="file" id="file-upload" accept="application/pdf" class="hidden">
                        
                        <textarea id="message-input" rows="1" placeholder="Explain your answer here..." class="flex-1 max-h-32 min-h-[44px] outline-none resize-none p-2 py-3 text-gray-700 bg-transparent" onkeydown="handleEnter(event)"></textarea>
                        
                        <button id="send-btn" onclick="sendMessage()" class="bg-indigo-600 hover:bg-indigo-700 text-white w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 transition-colors shadow-md disabled:opacity-50 disabled:cursor-not-allowed">
                            <i class="fa-solid fa-arrow-up"></i>
                        </button>
                    </div>
                    <div id="upload-status" class="text-center text-xs font-medium mt-1 h-4 pointer-events-auto"></div>
                    <p class="text-center text-xs text-gray-400 mt-2 font-medium pointer-events-auto">AI can make mistakes. Review the source material.</p>
                </div>
            </div>
        </div>

        <script>
            // --- STATE MANAGEMENT ---
            let currentUser = JSON.parse(localStorage.getItem('feynman_user'));
            let chatSessions = JSON.parse(localStorage.getItem('feynman_sessions')) || {};
            let currentSessionId = localStorage.getItem('feynman_active_session');

            // Close all dropdowns when clicking outside
            document.addEventListener('click', () => {
                document.querySelectorAll('.menu-dropdown').forEach(el => el.classList.add('hidden'));
            });

            // --- DOM ELEMENTS ---
            const authOverlay = document.getElementById('auth-overlay');
            const chatScrollWrapper = document.getElementById('chat-scroll-wrapper');
            const chatContainer = document.getElementById('chat-container');
            const historyList = document.getElementById('history-list');
            const messageInput = document.getElementById('message-input');
            const fileUpload = document.getElementById('file-upload');
            const uploadStatus = document.getElementById('upload-status');
            const sendBtn = document.getElementById('send-btn');
            
            // --- INITIALIZATION ---
            function init() {
                if (!currentUser) {
                    authOverlay.classList.remove('hidden');
                } else {
                    authOverlay.classList.add('hidden');
                    updateUserProfile();
                    
                    if (currentSessionId && chatSessions[currentSessionId]) {
                        loadSession(currentSessionId);
                    } else {
                        createNewChat(); // Won't clutter history until used
                    }
                    renderHistoryList();
                }
            }

            // --- AUTH LOGIC ---
            function handleEmailLogin(e) {
                e.preventDefault();
                const name = document.getElementById('auth-name').value;
                const email = document.getElementById('auth-email').value;
                loginUser({ name, email, initials: name.charAt(0).toUpperCase() });
            }

            function loginUser(userData) {
                currentUser = userData;
                localStorage.setItem('feynman_user', JSON.stringify(userData));
                init();
            }

            function signOut() {
                localStorage.removeItem('feynman_user');
                currentUser = null;
                init();
            }

            function updateUserProfile() {
                document.getElementById('user-name').innerText = currentUser.name;
                document.getElementById('user-email').innerText = currentUser.email;
                document.getElementById('user-avatar').innerText = currentUser.initials;
            }

            // --- SESSION MANAGEMENT ---
            function generateUUID() {
                return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                    var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
                    return v.toString(16);
                });
            }

            function createNewChat() {
                currentSessionId = generateUUID();
                localStorage.setItem('feynman_active_session', currentSessionId);
                
                // Do NOT add to chatSessions yet to prevent "Untitled Chat" spam
                
                document.getElementById('header-doc-title').innerText = "New Chat";
                updateMasteryUI(0);
                chatContainer.innerHTML = ''; 

                const introDiv = document.createElement('div');
                introDiv.className = "flex gap-4 w-full";
                introDiv.innerHTML = `
                    <div class="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0 text-indigo-600">
                        <i class="fa-solid fa-graduation-cap text-sm"></i>
                    </div>
                    <div class="bg-white border border-gray-200 p-5 rounded-2xl rounded-tl-sm shadow-sm max-w-[85%]">
                        <h3 class="font-bold text-gray-900 mb-2">Welcome to your interactive study session.</h3>
                        <p class="text-gray-600 mb-0">Upload a PDF using the paperclip icon below, or just say hello to get started.</p>
                    </div>
                `;
                chatContainer.appendChild(introDiv);
                renderHistoryList(); // Refresh list to un-highlight others
            }

            function switchSession(id) {
                currentSessionId = id;
                localStorage.setItem('feynman_active_session', currentSessionId);
                loadSession(id);
                renderHistoryList();
            }

            function saveSessions() {
                localStorage.setItem('feynman_sessions', JSON.stringify(chatSessions));
                localStorage.setItem('feynman_active_session', currentSessionId);
                renderHistoryList();
            }

            // --- 3-DOTS MENU LOGIC ---
            function toggleMenu(e, id) {
                e.stopPropagation();
                // Hide all other menus first
                document.querySelectorAll('.menu-dropdown').forEach(el => {
                    if (el.id !== `menu-${id}`) el.classList.add('hidden');
                });
                const menu = document.getElementById(`menu-${id}`);
                menu.classList.toggle('hidden');
            }

            function renameSession(e, id) {
                e.stopPropagation();
                document.getElementById(`menu-${id}`).classList.add('hidden');
                
                const session = chatSessions[id];
                const newName = prompt("Rename chat:", session.title);
                
                if (newName && newName.trim()) {
                    session.title = newName.trim();
                    if (currentSessionId === id) {
                        document.getElementById('header-doc-title').innerText = session.title;
                    }
                    saveSessions();
                }
            }

            function deleteSession(e, id) {
                e.stopPropagation();
                document.getElementById(`menu-${id}`).classList.add('hidden');
                
                if (confirm("Are you sure you want to delete this chat?")) {
                    delete chatSessions[id];
                    
                    if (currentSessionId === id) {
                        const remainingIds = Object.keys(chatSessions);
                        if (remainingIds.length > 0) {
                            switchSession(remainingIds[remainingIds.length - 1]);
                        } else {
                            createNewChat();
                        }
                    } else {
                        saveSessions();
                    }
                }
            }

            // --- UI RENDERING ---
            function renderHistoryList() {
                historyList.innerHTML = '';
                const sortedSessions = Object.values(chatSessions).reverse();
                
                sortedSessions.forEach(session => {
                    const li = document.createElement('li');
                    const isActive = session.id === currentSessionId ? 'chat-item-active' : 'chat-item';
                    const iconColor = session.hasDoc ? 'text-red-500' : 'text-gray-400';
                    
                    li.className = `cursor-pointer rounded-lg px-3 py-2.5 flex flex-col gap-1 group ${isActive}`;
                    li.onclick = () => switchSession(session.id);
                    
                    li.innerHTML = `
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2 overflow-hidden pr-2">
                                <i class="fa-solid fa-file-pdf ${iconColor} text-xs flex-shrink-0"></i>
                                <span class="text-sm font-semibold text-gray-800 truncate">${session.title}</span>
                            </div>
                            <div class="relative flex-shrink-0">
                                <button onclick="toggleMenu(event, '${session.id}')" class="text-gray-400 hover:text-gray-700 px-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <i class="fa-solid fa-ellipsis-vertical text-sm"></i>
                                </button>
                                <div id="menu-${session.id}" class="menu-dropdown hidden absolute right-0 mt-1 w-32 bg-white rounded-md border border-gray-100 z-50 py-1">
                                    <button onclick="renameSession(event, '${session.id}')" class="w-full text-left px-4 py-2 text-xs text-gray-700 hover:bg-gray-50 flex items-center gap-2">
                                        <i class="fa-solid fa-pen text-gray-400"></i> Rename
                                    </button>
                                    <button onclick="deleteSession(event, '${session.id}')" class="w-full text-left px-4 py-2 text-xs text-red-600 hover:bg-red-50 flex items-center gap-2">
                                        <i class="fa-solid fa-trash text-red-400"></i> Delete
                                    </button>
                                </div>
                            </div>
                        </div>
                        <div class="flex justify-between items-center px-4">
                             <span class="text-[10px] font-bold text-gray-400 uppercase">Mastery</span>
                             <span class="text-[10px] font-bold text-indigo-600">${session.mastery}%</span>
                        </div>
                    `;
                    historyList.appendChild(li);
                });
            }

            function loadSession(id) {
                const session = chatSessions[id];
                document.getElementById('header-doc-title').innerText = session.title;
                updateMasteryUI(session.mastery);
                chatContainer.innerHTML = ''; 

                const introDiv = document.createElement('div');
                introDiv.className = "flex gap-4 w-full";
                introDiv.innerHTML = `
                    <div class="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0 text-indigo-600">
                        <i class="fa-solid fa-graduation-cap text-sm"></i>
                    </div>
                    <div class="bg-white border border-gray-200 p-5 rounded-2xl rounded-tl-sm shadow-sm max-w-[85%]">
                        <h3 class="font-bold text-gray-900 mb-2">Welcome to your interactive study session.</h3>
                        <p class="text-gray-600 mb-0">Upload a PDF using the paperclip icon below, or continue your conversation.</p>
                    </div>
                `;
                chatContainer.appendChild(introDiv);

                session.history.forEach(msg => {
                    renderMessageUI(msg.role, msg.text, false);
                });

                chatScrollWrapper.scrollTop = chatScrollWrapper.scrollHeight;
            }

            // --- FILE UPLOAD LOGIC ---
            fileUpload.addEventListener('change', async (e) => {
                const file = e.target.files[0];
                if (!file) return;

                const formData = new FormData();
                formData.append('file', file);
                formData.append('session_id', currentSessionId); 

                uploadStatus.innerHTML = '<span class="text-indigo-600"><i class="fa-solid fa-circle-notch fa-spin"></i> Reading document...</span>';
                
                try {
                    const response = await fetch('/upload-document/', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        uploadStatus.innerHTML = `<span class="text-emerald-600"><i class="fa-solid fa-check-circle"></i> Loaded: ${file.name}</span>`;
                        setTimeout(() => uploadStatus.innerHTML = "", 3000);

                        // CREATE OR UPDATE SESSION ONLY ON SUCCESS
                        if (!chatSessions[currentSessionId]) {
                            chatSessions[currentSessionId] = {
                                id: currentSessionId,
                                title: file.name,
                                history: [],
                                mastery: 0,
                                hasDoc: true
                            };
                        } else {
                            chatSessions[currentSessionId].title = file.name;
                            chatSessions[currentSessionId].hasDoc = true;
                        }
                        
                        document.getElementById('header-doc-title').innerText = file.name;
                        
                        const welcomeText = `I have successfully analyzed **${file.name}**.\\n\\nLet's begin. What is the core concept discussed in this material? Try to explain it to me in your own words.`;
                        
                        chatSessions[currentSessionId].history.push({role: 'ai', text: welcomeText});
                        saveSessions();
                        renderMessageUI('ai', welcomeText, true);

                    } else {
                        uploadStatus.innerHTML = `<span class="text-red-500"><i class="fa-solid fa-triangle-exclamation"></i> Error: ${data.detail}</span>`;
                    }
                } catch (error) {
                    uploadStatus.innerHTML = `<span class="text-red-500"><i class="fa-solid fa-triangle-exclamation"></i> Server offline.</span>`;
                }
            });

            // --- CHAT LOGIC ---
            messageInput.addEventListener('input', function() {
                this.style.height = 'auto';
                this.style.height = (this.scrollHeight) + 'px';
            });

            function handleEnter(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            }

            function sendHintRequest() {
                messageInput.value = "I'm stuck. Can you give me a clear, detailed explanation with an analogy to help me understand?";
                sendMessage();
            }

            async function sendMessage() {
                const text = messageInput.value.trim();
                if (!text) return;

                // Create session if it's the very first message
                if (!chatSessions[currentSessionId]) {
                     chatSessions[currentSessionId] = {
                        id: currentSessionId,
                        title: text.length > 25 ? text.substring(0, 25) + '...' : text,
                        history: [],
                        mastery: 0,
                        hasDoc: false
                    };
                }

                renderMessageUI('user', text, true);
                chatSessions[currentSessionId].history.push({role: 'user', text: text});
                saveSessions();

                messageInput.value = '';
                messageInput.style.height = 'auto';
                sendBtn.disabled = true;
                sendBtn.innerHTML = '<i class="fa-solid fa-ellipsis fa-fade"></i>';

                try {
                    const response = await fetch('/tutor-chat/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ 
                            session_id: currentSessionId,
                            user_message: text 
                        })
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        let aiText = data.response;
                        const masteryRegex = /\\[MASTERY:\\s*(\\d+)%\\]/i;
                        const match = aiText.match(masteryRegex);
                        
                        if (match) {
                            const score = parseInt(match[1]);
                            chatSessions[currentSessionId].mastery = score;
                            updateMasteryUI(score);
                            aiText = aiText.replace(masteryRegex, '').trim(); 
                        }
                        
                        chatSessions[currentSessionId].history.push({role: 'ai', text: aiText});
                        saveSessions();
                        renderMessageUI('ai', aiText, true);
                    } else {
                        // Revert on failure
                        chatSessions[currentSessionId].history.pop();
                        if(chatSessions[currentSessionId].history.length === 0 && !chatSessions[currentSessionId].hasDoc) {
                             delete chatSessions[currentSessionId];
                        }
                        saveSessions();

                        if(data.detail === "NO_DOCUMENT") {
                            renderMessageUI('system', `<span class="text-amber-500"><i class="fa-solid fa-circle-info"></i> Please attach a PDF document using the paperclip icon first so I have material to tutor you on!</span>`, true);
                        } else {
                            renderMessageUI('system', `<span class="text-red-500"><i class="fa-solid fa-triangle-exclamation"></i> Error: ${data.detail}</span>`, true);
                        }
                    }
                } catch (error) {
                    renderMessageUI('system', `<span class="text-red-500"><i class="fa-solid fa-triangle-exclamation"></i> Failed to connect to server.</span>`, true);
                } finally {
                    sendBtn.disabled = false;
                    sendBtn.innerHTML = '<i class="fa-solid fa-arrow-up"></i>';
                }
            }

            function updateMasteryUI(score) {
                const bar = document.getElementById('mastery-bar');
                const text = document.getElementById('mastery-text');
                bar.style.width = score + '%';
                text.innerText = score + '%';
                
                if (score < 40) bar.className = "h-full rounded-full transition-all duration-1000 ease-out bg-amber-500";
                else if (score < 80) bar.className = "h-full rounded-full transition-all duration-1000 ease-out bg-indigo-500";
                else bar.className = "h-full rounded-full transition-all duration-1000 ease-out bg-emerald-500";
            }

            function renderMessageUI(role, text, animate) {
                const div = document.createElement('div');
                div.className = "flex gap-4 w-full " + (animate ? "opacity-0 translate-y-4 transition-all duration-500 ease-out" : "");
                
                if (role === 'user') {
                    div.classList.add('flex-row-reverse');
                    div.innerHTML = `
                        <div class="w-8 h-8 rounded-full bg-gray-800 flex items-center justify-center flex-shrink-0 text-white shadow-md text-xs font-bold">
                            ${currentUser ? currentUser.initials : 'U'}
                        </div>
                        <div class="bg-indigo-600 text-white p-4 rounded-2xl rounded-tr-sm shadow-sm max-w-[80%] markdown-body" style="color: white !important;">
                            ${text}
                        </div>
                    `;
                } else {
                    div.innerHTML = `
                        <div class="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0 text-indigo-600 shadow-sm">
                            <i class="fa-solid fa-graduation-cap text-sm"></i>
                        </div>
                        <div class="bg-white border border-gray-200 text-gray-800 p-5 rounded-2xl rounded-tl-sm shadow-sm max-w-[85%] markdown-body">
                            ${marked.parse(text)}
                        </div>
                    `;
                }

                chatContainer.appendChild(div);
                
                if (animate) {
                    setTimeout(() => div.classList.remove('opacity-0', 'translate-y-4'), 50);
                }
                chatScrollWrapper.scrollTop = chatScrollWrapper.scrollHeight;
            }

            // Boot the app
            init();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)