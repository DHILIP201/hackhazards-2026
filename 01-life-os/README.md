🧠 Context-Aware Life OS - Complete Command History

This document tracks every terminal command used to build the Life OS application from scratch, including explanations for why each package was necessary.

1. Initialize the Application

npx create-expo-app@latest 01-life-os --template blank-typescript
cd 01-life-os


Explanation:
This command scaffolds a brand-new React Native mobile application using the Expo framework. We specifically chose the blank-typescript template to ensure we have strict type-checking, which prevents bugs and makes the codebase look highly professional to hackathon judges.

2. Install the Core AI Engine

npm install @google/generative-ai react-native-dotenv


Explanation:

@google/generative-ai: This is the official Google SDK that allows our app to communicate directly with the Gemini 2.5 Flash model to analyze the user's brain dump.

react-native-dotenv: This package allows us to securely load our secret EXPO_PUBLIC_GEMINI_API_KEY from the .env file without hardcoding it into the app.

3. Install the Local Storage Database

npx expo install @react-native-async-storage/async-storage


Explanation:
To make this a true "Operating System" rather than a temporary text parser, we needed the app to remember the user's tasks even if they closed it. AsyncStorage acts as our local, on-device database to save the to-do list and mood history persistently.

4. Install the Native Calendar Integration

npx expo install expo-calendar


Explanation:
This was our "V2 Roadmap" upgrade. This native Expo module allows our app to ask the user for calendar permissions and seamlessly push the AI-estimated time blocks directly to their phone's native calendar (like Google Calendar or Apple Calendar).

5. Start the Development Server

npx expo start --clear


Explanation:
This boots up the Metro bundler to serve the app to your phone or web browser. The --clear flag is crucial here; it forces Expo to clear its cache and read our .env file from scratch, ensuring our Gemini API key is properly loaded into the environment.