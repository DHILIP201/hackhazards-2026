import React, { useState, useEffect } from 'react';
import { 
  StyleSheet, 
  Text, 
  View, 
  TextInput, 
  TouchableOpacity, 
  ScrollView, 
  ActivityIndicator, 
  KeyboardAvoidingView, 
  Platform,
  SafeAreaView,
  StatusBar,
  LayoutAnimation,
  UIManager
} from 'react-native';
import { GoogleGenerativeAI } from '@google/generative-ai';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Calendar from 'expo-calendar';

// Enable LayoutAnimation for Android
if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

// Initialize the Gemini AI Engine
const apiKey = process.env.EXPO_PUBLIC_GEMINI_API_KEY || '';
const genAI = new GoogleGenerativeAI(apiKey);

export default function App() {
  const [entry, setEntry] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isListening, setIsListening] = useState(false);
  
  const [currentMood, setCurrentMood] = useState<string | null>(null);
  const [currentAdvice, setCurrentAdvice] = useState<string | null>(null);
  const [savedTasks, setSavedTasks] = useState<any[]>([]);
  const [moodHistory, setMoodHistory] = useState<any[]>([]);
  
  const [activeTab, setActiveTab] = useState<'dump' | 'tasks' | 'analytics'>('dump');

  useEffect(() => {
    loadSavedData();
  }, []);

  const loadSavedData = async () => {
    try {
      const storedTasks = await AsyncStorage.getItem('@life_os_tasks');
      const storedMood = await AsyncStorage.getItem('@life_os_mood');
      const storedAdvice = await AsyncStorage.getItem('@life_os_advice');
      const storedHistory = await AsyncStorage.getItem('@life_os_history');
      
      if (storedTasks) setSavedTasks(JSON.parse(storedTasks));
      if (storedMood) setCurrentMood(storedMood);
      if (storedAdvice) setCurrentAdvice(storedAdvice);
      if (storedHistory) setMoodHistory(JSON.parse(storedHistory));
    } catch (e) {
      console.error("Failed to load data", e);
    }
  };

  const saveState = async (key: string, value: any) => {
    try {
      await AsyncStorage.setItem(key, typeof value === 'string' ? value : JSON.stringify(value));
    } catch (e) {
      console.error(`Failed to save ${key}`, e);
    }
  };

  const clearAllData = async () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    try {
      await AsyncStorage.clear();
      setSavedTasks([]);
      setCurrentMood(null);
      setCurrentAdvice(null);
      setMoodHistory([]);
      setEntry('');
      setActiveTab('dump');
    } catch(e) {
      console.error("Failed to clear data", e);
    }
  }

  const switchTab = (tab: 'dump' | 'tasks' | 'analytics') => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setActiveTab(tab);
  };

  const toggleVoiceRecording = () => {
    if (Platform.OS === 'web' && ('webkitSpeechRecognition' in window)) {
      const SpeechRecognition = (window as any).webkitSpeechRecognition;
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;

      recognition.onstart = () => setIsListening(true);
      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setEntry(transcript);
      };
      recognition.onend = () => setIsListening(false);
      recognition.onerror = () => setIsListening(false);
      
      recognition.start();
    } else {
      alert("🎙️ On mobile devices, please use the microphone icon on your native keyboard to dictate!");
    }
  };

  const syncToCalendar = async (taskText: string) => {
    const { status } = await Calendar.requestCalendarPermissionsAsync();
    if (status === 'granted') {
      const calendars = await Calendar.getCalendarsAsync(Calendar.EntityTypes.EVENT);
      const defaultCalendar = calendars.find(cal => cal.isPrimary) || calendars[0];
      
      if (defaultCalendar) {
         const startDate = new Date();
         startDate.setHours(startDate.getHours() + 1);
         const endDate = new Date(startDate);
         endDate.setHours(endDate.getHours() + 1);

         try {
           await Calendar.createEventAsync(defaultCalendar.id, {
             title: taskText,
             startDate,
             endDate,
             notes: 'Scheduled by Life OS',
           });
           alert('✅ Successfully synced to Calendar!');
         } catch (e) {
           alert('Failed to sync. Make sure your calendar is set up.');
         }
      }
    } else {
      alert('⚠️ Calendar permission is required.');
    }
  };

  const analyzeJournalEntry = async () => {
    if (!entry.trim()) return;
    setIsAnalyzing(true);

    try {
      const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash" });
      const prompt = `
        You are Nova AI, the brain of an elite Life OS. 
        Analyze the following chaotic journal entry from the user.
        1. Identify their mood (1-2 words + emoji).
        2. Provide 1 short sentence of empathetic coaching advice.
        3. Extract actionable tasks. For each task, assign:
           - "timeBlock": Suggested duration/context (e.g., "Deep Work (1h)")
           - "category": Broad bucket (e.g., "💼 Work", "🏠 Personal", "💪 Health")
           - "priority": Only use "High", "Medium", or "Low"
        
        Return ONLY valid JSON:
        {
          "mood": "Focused 🎯",
          "advice": "You're in the zone! Knock out the hardest tasks first.",
          "tasks": [
            { "text": "Finish the hackathon code", "timeBlock": "Deep Work (2h)", "category": "💼 Work", "priority": "High" }
          ]
        }
        Journal Entry: "${entry}"
      `;

      const aiResponse = await model.generateContent(prompt);
      const cleanJson = aiResponse.response.text().replace(/```json/g, '').replace(/```/g, '').trim();
      const parsedData = JSON.parse(cleanJson);
      
      LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);

      setCurrentMood(parsedData.mood);
      setCurrentAdvice(parsedData.advice);
      saveState('@life_os_mood', parsedData.mood);
      saveState('@life_os_advice', parsedData.advice);

      const newHistoryItem = { 
        date: new Date().toLocaleDateString() + ' ' + new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}), 
        mood: parsedData.mood 
      };
      const updatedHistory = [newHistoryItem, ...moodHistory];
      setMoodHistory(updatedHistory);
      saveState('@life_os_history', updatedHistory);

      if (parsedData.tasks && parsedData.tasks.length > 0) {
        const newTasks = parsedData.tasks.map((t: any) => ({
          id: Date.now().toString() + Math.random().toString(),
          ...t
        }));
        const updatedTasks = [...newTasks, ...savedTasks];
        setSavedTasks(updatedTasks);
        saveState('@life_os_tasks', updatedTasks);
        setActiveTab('tasks');
      } else {
        alert("Mood logged! No actionable tasks detected.");
      }
      setEntry('');
    } catch (error) {
      console.error("AI Analysis Failed:", error);
      alert("Analysis failed. Please check your API key.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const completeTask = (taskId: string) => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    const updatedTasks = savedTasks.filter(task => task.id !== taskId);
    setSavedTasks(updatedTasks);
    saveState('@life_os_tasks', updatedTasks);
  };

  const getPriorityColor = (priority: string) => {
    switch(priority) {
      case 'High': return '#EF4444'; // Red
      case 'Medium': return '#F59E0B'; // Amber
      case 'Low': return '#10B981'; // Emerald
      default: return '#6B7280';
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#0B0914" />
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.keyboardView}>
        <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
          
          {/* Top Navbar */}
          <View style={styles.headerTop}>
            <View>
              <Text style={styles.title}>Life OS</Text>
              <Text style={styles.subtitle}>Context-Aware Intelligence</Text>
            </View>
            <TouchableOpacity onPress={clearAllData} style={styles.clearButton}>
              <Text style={styles.clearButtonText}>Reset Data</Text>
            </TouchableOpacity>
          </View>

          {/* AI Insight Dashboard */}
          {(currentMood || currentAdvice) && (
            <View style={styles.dashboardCard}>
              {currentMood && (
                <View style={styles.moodRow}>
                  <View style={styles.pulseDot} />
                  <Text style={styles.moodText}>Current Vibe: <Text style={styles.moodHighlight}>{currentMood}</Text></Text>
                </View>
              )}
              {currentAdvice && (
                <View style={styles.adviceWrapper}>
                  <Text style={styles.adviceLabel}>✨ NOVA AI INSIGHT</Text>
                  <Text style={styles.adviceText}>{currentAdvice}</Text>
                </View>
              )}
            </View>
          )}
          
          {/* Custom Tab Navigation */}
          <View style={styles.tabContainer}>
            <TouchableOpacity style={[styles.tab, activeTab === 'dump' && styles.activeTab]} onPress={() => switchTab('dump')}>
              <Text style={[styles.tabText, activeTab === 'dump' && styles.activeTabText]}>Console</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.tab, activeTab === 'tasks' && styles.activeTab]} onPress={() => switchTab('tasks')}>
              <Text style={[styles.tabText, activeTab === 'tasks' && styles.activeTabText]}>
                Tasks {savedTasks.length > 0 && `(${savedTasks.length})`}
              </Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.tab, activeTab === 'analytics' && styles.activeTab]} onPress={() => switchTab('analytics')}>
              <Text style={[styles.tabText, activeTab === 'analytics' && styles.activeTabText]}>Analytics</Text>
            </TouchableOpacity>
          </View>

          {/* TAB 1: CONSOLE (The New Integrated Input) */}
          {activeTab === 'dump' && (
            <View style={styles.integratedConsole}>
              <TextInput
                style={styles.consoleInput}
                placeholder="Offload your thoughts here. Let Nova AI handle the rest..."
                placeholderTextColor="#6B6396"
                multiline
                value={entry}
                onChangeText={setEntry}
                textAlignVertical="top"
              />
              
              <View style={styles.consoleFooter}>
                <View style={styles.modelIndicator}>
                  <Text style={styles.modelIndicatorText}>✨ Nova Flash</Text>
                </View>

                <View style={styles.consoleActions}>
                  <TouchableOpacity 
                    style={[styles.iconButton, isListening && styles.iconButtonActive]} 
                    onPress={toggleVoiceRecording}
                  >
                    <Text style={styles.iconText}>{isListening ? "🔴" : "🎙️"}</Text>
                  </TouchableOpacity>

                  <TouchableOpacity 
                    style={[styles.submitButton, !entry.trim() && styles.submitButtonDisabled]} 
                    onPress={analyzeJournalEntry}
                    disabled={!entry.trim() || isAnalyzing}
                  >
                    {isAnalyzing ? (
                      <ActivityIndicator color="#FFF" size="small" />
                    ) : (
                      <Text style={styles.submitIcon}>↑</Text>
                    )}
                  </TouchableOpacity>
                </View>
              </View>
            </View>
          )}

          {/* TAB 2: TASKS */}
          {activeTab === 'tasks' && (
            <View style={styles.tasksWrapper}>
              {savedTasks.length > 0 ? (
                savedTasks.map((task) => (
                  <View key={task.id} style={styles.taskCard}>
                    <TouchableOpacity onPress={() => completeTask(task.id)} style={styles.checkbox} />
                    
                    <View style={styles.taskContent}>
                      <Text style={styles.taskCardText}>{task.text}</Text>
                      
                      <View style={styles.taskBadgesRow}>
                        {task.category && (
                          <Text style={styles.categoryText}>{task.category}</Text>
                        )}
                        {task.timeBlock && (
                          <View style={styles.timeBlockBadge}>
                            <Text style={styles.timeBlockText}>{task.timeBlock}</Text>
                          </View>
                        )}
                        {task.priority && (
                          <View style={[styles.priorityBadge, { borderColor: getPriorityColor(task.priority) }]}>
                            <View style={[styles.priorityDot, { backgroundColor: getPriorityColor(task.priority) }]} />
                            <Text style={[styles.priorityText, { color: getPriorityColor(task.priority) }]}>{task.priority}</Text>
                          </View>
                        )}
                      </View>
                    </View>

                    <TouchableOpacity onPress={() => syncToCalendar(task.text)} style={styles.calendarAction}>
                      <Text style={styles.calendarIcon}>📅</Text>
                    </TouchableOpacity>
                  </View>
                ))
              ) : (
                <View style={styles.emptyStateContainer}>
                  <Text style={styles.emptyStateIcon}>🧘‍♂️</Text>
                  <Text style={styles.emptyStateTitle}>Inbox Zero</Text>
                  <Text style={styles.emptyStateDesc}>Your mind is clear. Nothing to do right now.</Text>
                </View>
              )}
            </View>
          )}

          {/* TAB 3: ANALYTICS */}
          {activeTab === 'analytics' && (
            <View style={styles.analyticsWrapper}>
              <Text style={styles.sectionHeader}>Mood Timeline</Text>
              {moodHistory.length > 0 ? (
                moodHistory.map((item, index) => (
                  <View key={index} style={styles.historyCard}>
                    <Text style={styles.historyDate}>{item.date}</Text>
                    <Text style={styles.historyMood}>{item.mood}</Text>
                  </View>
                ))
              ) : (
                <View style={styles.emptyStateContainer}>
                  <Text style={styles.emptyStateDesc}>Dump your thoughts to generate analytics over time.</Text>
                </View>
              )}
            </View>
          )}

        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0B0914' },
  keyboardView: { flex: 1 },
  scrollContent: { padding: 20, paddingBottom: 40 },
  
  headerTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, marginTop: 10 },
  title: { fontSize: 32, fontWeight: '800', color: '#FFFFFF', letterSpacing: -1 },
  subtitle: { fontSize: 14, color: '#8B84B5', fontWeight: '500', marginTop: 4 },
  clearButton: { paddingVertical: 8, paddingHorizontal: 16, backgroundColor: 'rgba(239, 68, 68, 0.1)', borderRadius: 20 },
  clearButtonText: { color: '#FCA5A5', fontSize: 13, fontWeight: '600' },

  dashboardCard: { backgroundColor: '#151226', borderRadius: 20, padding: 20, borderWidth: 1, borderColor: '#2A2447', marginBottom: 24 },
  moodRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 16 },
  pulseDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: '#A78BFA', marginRight: 12, shadowColor: '#A78BFA', shadowOffset: { width: 0, height: 0 }, shadowOpacity: 1, shadowRadius: 8 },
  moodText: { color: '#8B84B5', fontSize: 15, fontWeight: '500' },
  moodHighlight: { color: '#FFFFFF', fontWeight: '700' },
  adviceWrapper: { backgroundColor: 'rgba(234, 179, 8, 0.08)', padding: 16, borderRadius: 12, borderWidth: 1, borderColor: 'rgba(234, 179, 8, 0.2)' },
  adviceLabel: { color: '#FDE047', fontSize: 11, fontWeight: '800', letterSpacing: 1, marginBottom: 8 },
  adviceText: { color: '#E2E8F0', fontSize: 15, lineHeight: 22 },

  tabContainer: { flexDirection: 'row', backgroundColor: '#151226', borderRadius: 16, padding: 5, marginBottom: 20 },
  tab: { flex: 1, paddingVertical: 12, alignItems: 'center', borderRadius: 12 },
  activeTab: { backgroundColor: '#2A2447', shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.2, shadowRadius: 4 },
  tabText: { color: '#8B84B5', fontWeight: '600', fontSize: 14 },
  activeTabText: { color: '#FFFFFF' },

  // THE NEW INTEGRATED CONSOLE
  integratedConsole: { backgroundColor: '#151226', borderRadius: 24, borderWidth: 1, borderColor: '#2A2447', overflow: 'hidden' },
  consoleInput: { color: '#FFFFFF', fontSize: 16, padding: 24, minHeight: 200, lineHeight: 24 },
  consoleFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 12, backgroundColor: '#0B0914', borderTopWidth: 1, borderTopColor: '#2A2447' },
  modelIndicator: { flexDirection: 'row', alignItems: 'center', backgroundColor: 'rgba(124, 58, 237, 0.15)', paddingVertical: 6, paddingHorizontal: 12, borderRadius: 20 },
  modelIndicatorText: { color: '#C4B5FD', fontSize: 12, fontWeight: '700' },
  consoleActions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  iconButton: { width: 40, height: 40, borderRadius: 20, backgroundColor: '#151226', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#2A2447' },
  iconButtonActive: { backgroundColor: 'rgba(239, 68, 68, 0.2)', borderColor: '#EF4444' },
  iconText: { fontSize: 16 },
  submitButton: { width: 40, height: 40, borderRadius: 20, backgroundColor: '#7C3AED', alignItems: 'center', justifyContent: 'center' },
  submitButtonDisabled: { backgroundColor: '#2A2447' },
  submitIcon: { color: '#FFF', fontSize: 20, fontWeight: 'bold', marginTop: -2 },

  // TASKS
  tasksWrapper: { gap: 12 },
  taskCard: { flexDirection: 'row', backgroundColor: '#151226', padding: 16, borderRadius: 20, borderWidth: 1, borderColor: '#2A2447', alignItems: 'center' },
  checkbox: { width: 24, height: 24, borderRadius: 8, borderWidth: 2, borderColor: '#7C3AED', marginRight: 16 },
  taskContent: { flex: 1 },
  taskCardText: { color: '#FFFFFF', fontSize: 16, lineHeight: 22, marginBottom: 10 },
  taskBadgesRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, alignItems: 'center' },
  categoryText: { color: '#8B84B5', fontSize: 13, fontWeight: '600' },
  timeBlockBadge: { backgroundColor: 'rgba(124, 58, 237, 0.15)', paddingVertical: 4, paddingHorizontal: 8, borderRadius: 8 },
  timeBlockText: { color: '#C4B5FD', fontSize: 12, fontWeight: '600' },
  priorityBadge: { flexDirection: 'row', alignItems: 'center', paddingVertical: 4, paddingHorizontal: 8, borderRadius: 8, borderWidth: 1 },
  priorityDot: { width: 6, height: 6, borderRadius: 3, marginRight: 6 },
  priorityText: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase' },
  calendarAction: { padding: 10, backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: 12, marginLeft: 10 },
  calendarIcon: { fontSize: 18 },

  // ANALYTICS & SHARED
  analyticsWrapper: { gap: 12 },
  sectionHeader: { color: '#FFFFFF', fontSize: 18, fontWeight: '700', marginBottom: 8 },
  historyCard: { flexDirection: 'row', justifyContent: 'space-between', backgroundColor: '#151226', padding: 16, borderRadius: 16, borderWidth: 1, borderColor: '#2A2447' },
  historyDate: { color: '#8B84B5', fontSize: 14, fontWeight: '500' },
  historyMood: { color: '#FFFFFF', fontSize: 16, fontWeight: '600' },
  emptyStateContainer: { padding: 40, alignItems: 'center', backgroundColor: '#151226', borderRadius: 24, borderWidth: 1, borderColor: '#2A2447', borderStyle: 'dashed', marginTop: 20 },
  emptyStateIcon: { fontSize: 48, marginBottom: 16 },
  emptyStateTitle: { color: '#FFFFFF', fontSize: 20, fontWeight: '700', marginBottom: 8 },
  emptyStateDesc: { color: '#8B84B5', fontSize: 15, textAlign: 'center', lineHeight: 22 }
});