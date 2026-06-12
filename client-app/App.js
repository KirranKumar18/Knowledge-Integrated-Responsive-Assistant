import React, { useState, useEffect, useRef } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  ScrollView,
  SafeAreaView,
  StatusBar,
  ActivityIndicator,
  Animated,
  Modal,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { Audio } from 'expo-av';
import * as Speech from 'expo-speech';
import * as SecureStore from 'expo-secure-store';
import { LinearGradient } from 'expo-linear-gradient';

const DEFAULT_SERVER = 'http://localhost:8000';

export default function App() {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [serverUrl, setServerUrl] = useState(DEFAULT_SERVER);
  const [showSettings, setShowSettings] = useState(false);
  const [tempServerUrl, setTempServerUrl] = useState(DEFAULT_SERVER);
  const [sessionId, setSessionId] = useState('');
  const [connectionStatus, setConnectionStatus] = useState('Checking...');

  const scrollViewRef = useRef();
  const recordingRef = useRef(null);

  // Pulse animation values
  const pulseAnim1 = useRef(new Animated.Value(1)).current;
  const pulseAnim2 = useRef(new Animated.Value(1)).current;
  const pulseAnim3 = useRef(new Animated.Value(1)).current;

  // Generate session ID on mount
  useEffect(() => {
    const newSessionId = Math.random().toString(36).substring(2, 15);
    setSessionId(newSessionId);
    
    // Load saved server URL
    SecureStore.getItemAsync('server_url').then((url) => {
      if (url) {
        setServerUrl(url);
        setTempServerUrl(url);
        checkHealth(url);
      } else {
        checkHealth(DEFAULT_SERVER);
      }
    });

    // Add initial greeting
    setMessages([
      {
        id: '1',
        text: 'Hello! I am KIRA, your personal voice assistant. How can I help you today?',
        sender: 'kira',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  }, []);

  // Pulse visualizer loop
  useEffect(() => {
    if (isRecording || isSpeaking) {
      Animated.loop(
        Animated.parallel([
          Animated.sequence([
            Animated.timing(pulseAnim1, { toValue: 1.8, duration: 1000, useNativeDriver: true }),
            Animated.timing(pulseAnim1, { toValue: 1.0, duration: 1000, useNativeDriver: true }),
          ]),
          Animated.sequence([
            Animated.delay(300),
            Animated.timing(pulseAnim2, { toValue: 2.2, duration: 1000, useNativeDriver: true }),
            Animated.timing(pulseAnim2, { toValue: 1.0, duration: 1000, useNativeDriver: true }),
          ]),
          Animated.sequence([
            Animated.delay(600),
            Animated.timing(pulseAnim3, { toValue: 2.5, duration: 1000, useNativeDriver: true }),
            Animated.timing(pulseAnim3, { toValue: 1.0, duration: 1000, useNativeDriver: true }),
          ]),
        ])
      ).start();
    } else {
      pulseAnim1.setValue(1);
      pulseAnim2.setValue(1);
      pulseAnim3.setValue(1);
    }
  }, [isRecording, isSpeaking]);

  const checkHealth = async (url) => {
    try {
      const response = await fetch(`${url}/health`, { method: 'GET', signal: AbortSignal.timeout(4000) });
      if (response.status === 200) {
        setConnectionStatus('Online ✓');
      } else {
        setConnectionStatus('Server Error ❌');
      }
    } catch (err) {
      setConnectionStatus('Offline ❌');
    }
  };

  const handleSaveSettings = async () => {
    let cleanUrl = tempServerUrl.trim().replace(/\/$/, '');
    if (!/^https?:\/\//i.test(cleanUrl)) {
      cleanUrl = 'http://' + cleanUrl;
    }
    setServerUrl(cleanUrl);
    setTempServerUrl(cleanUrl);
    await SecureStore.setItemAsync('server_url', cleanUrl);
    setShowSettings(false);
    setConnectionStatus('Checking...');
    checkHealth(cleanUrl);
  };

  // Audio Recording Handlers
  const startRecording = async () => {
    try {
      // Stop KIRA speaking first
      if (isSpeaking) {
        Speech.stop();
        setIsSpeaking(false);
      }

      await Audio.requestPermissionsAsync();
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      recordingRef.current = recording;
      setIsRecording(true);
    } catch (err) {
      alert('Failed to start recording: ' + err.message);
    }
  };

  const stopRecording = async () => {
    if (!recordingRef.current) return;
    setIsRecording(false);
    try {
      await recordingRef.current.stopAndUnloadAsync();
      const uri = recordingRef.current.getURI();
      recordingRef.current = null;
      if (uri) {
        uploadVoiceFile(uri);
      }
    } catch (err) {
      alert('Failed to stop recording: ' + err.message);
    }
  };

  const uploadVoiceFile = async (uri) => {
    setIsProcessing(true);
    
    // Add temporary message for user speaking
    const tempUserMsgId = Math.random().toString();
    setMessages((prev) => [
      ...prev,
      {
        id: tempUserMsgId,
        text: '🎤 [Voice message sent]',
        sender: 'user',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);

    try {
      const formData = new FormData();
      formData.append('audio', {
        uri: uri,
        name: 'audio.m4a',
        type: 'audio/m4a',
      });
      if (sessionId) {
        formData.append('session_id', sessionId);
      }

      const response = await fetch(`${serverUrl}/voice`, {
        method: 'POST',
        body: formData,
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.status === 200) {
        const data = await response.json();
        
        // Update user message with the real transcription
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === tempUserMsgId && data.transcription
              ? { ...msg, text: data.transcription }
              : msg
          )
        );

        // Add KIRA response
        const kiraReply = data.response || "I didn't receive a response.";
        addKiraMessage(kiraReply);
      } else {
        addKiraMessage('Error: Server returned status ' + response.status);
      }
    } catch (err) {
      addKiraMessage('Error: Unable to reach KIRA server. Make sure Ngrok/Server is running.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSendText = async () => {
    if (!inputText.trim()) return;
    const userText = inputText.trim();
    setInputText('');
    setIsProcessing(true);

    // Stop KIRA speaking
    if (isSpeaking) {
      Speech.stop();
      setIsSpeaking(false);
    }

    // Add user message
    setMessages((prev) => [
      ...prev,
      {
        id: Math.random().toString(),
        text: userText,
        sender: 'user',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);

    try {
      const response = await fetch(`${serverUrl}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userText,
          session_id: sessionId,
        }),
      });

      if (response.status === 200) {
        const data = await response.json();
        addKiraMessage(data.response);
      } else {
        addKiraMessage('Error: Server returned status ' + response.status);
      }
    } catch (err) {
      addKiraMessage('Error: Unable to reach KIRA server. Make sure Ngrok/Server is running.');
    } finally {
      setIsProcessing(false);
    }
  };

  const addKiraMessage = (text) => {
    setMessages((prev) => [
      ...prev,
      {
        id: Math.random().toString(),
        text: text,
        sender: 'kira',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
    
    // Speak KIRA's response
    setIsSpeaking(true);
    Speech.speak(text, {
      language: 'en',
      onDone: () => setIsSpeaking(false),
      onError: () => setIsSpeaking(false),
    });
  };

  const handleResetSession = () => {
    const newSessionId = Math.random().toString(36).substring(2, 15);
    setSessionId(newSessionId);
    setMessages([
      {
        id: '1',
        text: 'Session reset! KIRA is ready for a new conversation.',
        sender: 'kira',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
    if (isSpeaking) {
      Speech.stop();
      setIsSpeaking(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" />
      <LinearGradient colors={['#080810', '#101026']} style={styles.gradient}>
        
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.headerTitle}>KIRA ASSISTANT</Text>
            <View style={styles.statusContainer}>
              <View style={[styles.statusDot, { backgroundColor: connectionStatus.includes('Online') ? '#00E5FF' : '#FF5252' }]} />
              <Text style={styles.headerSubtitle}>{connectionStatus}</Text>
            </View>
          </View>
          <View style={styles.headerActions}>
            <TouchableOpacity onPress={handleResetSession} style={styles.headerButton}>
              <Text style={styles.headerButtonText}>🔄 Reset</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => setShowSettings(true)} style={styles.headerButton}>
              <Text style={styles.headerButtonText}>⚙️ Settings</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Messages List */}
        <ScrollView
          ref={scrollViewRef}
          contentContainerStyle={styles.messagesContainer}
          onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: true })}
        >
          {messages.map((item) => (
            <View
              key={item.id}
              style={[
                styles.messageWrapper,
                item.sender === 'user' ? styles.userWrapper : styles.kiraWrapper,
              ]}
            >
              <LinearGradient
                colors={item.sender === 'user' ? ['#2E1A47', '#1A0E2A'] : ['#1C1C30', '#121220']}
                style={[
                  styles.messageBubble,
                  item.sender === 'user' ? styles.userBubble : styles.kiraBubble,
                ]}
              >
                <Text style={styles.messageText}>{item.text}</Text>
                <Text style={styles.messageTime}>{item.timestamp}</Text>
              </LinearGradient>
            </View>
          ))}
          {isProcessing && (
            <View style={[styles.messageWrapper, styles.kiraWrapper]}>
              <View style={[styles.messageBubble, styles.kiraBubble, styles.loadingBubble]}>
                <ActivityIndicator size="small" color="#00E5FF" />
                <Text style={[styles.messageText, { marginLeft: 8 }]}>Thinking...</Text>
              </View>
            </View>
          )}
        </ScrollView>

        {/* Visual Feedback Anim Container */}
        <View style={styles.visualizerContainer}>
          {(isRecording || isSpeaking) && (
            <View style={styles.pulseContainer}>
              <Animated.View style={[styles.pulseCircle, { transform: [{ scale: pulseAnim3 }], opacity: 0.15 }]} />
              <Animated.View style={[styles.pulseCircle, { transform: [{ scale: pulseAnim2 }], opacity: 0.25 }]} />
              <Animated.View style={[styles.pulseCircle, { transform: [{ scale: pulseAnim1 }], opacity: 0.45 }]} />
            </View>
          )}
          
          {/* Main Record/Status Button */}
          <TouchableOpacity
            onPressIn={startRecording}
            onPressOut={stopRecording}
            style={[
              styles.micButton,
              isRecording && styles.micButtonActive,
            ]}
          >
            <Text style={styles.micIcon}>
              {isRecording ? '🎙️' : isSpeaking ? '🔊' : '🎙️'}
            </Text>
          </TouchableOpacity>
          <Text style={styles.micHelpText}>
            {isRecording ? 'Listening... Release to send' : 'Hold Mic to Speak'}
          </Text>
        </View>

        {/* Text Input Row */}
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
        >
          <View style={styles.inputContainer}>
            <TextInput
              style={styles.textInput}
              placeholder="Type message for KIRA..."
              placeholderTextColor="#666680"
              value={inputText}
              onChangeText={setInputText}
              onSubmitEditing={handleSendText}
            />
            <TouchableOpacity onPress={handleSendText} style={styles.sendButton}>
              <Text style={styles.sendButtonText}>Send</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>

        {/* Settings Modal */}
        <Modal visible={showSettings} animationType="slide" transparent={true}>
          <View style={styles.modalOverlay}>
            <LinearGradient colors={['#14142B', '#0A0A14']} style={styles.modalContent}>
              <Text style={styles.modalTitle}>KIRA Settings</Text>
              
              <Text style={styles.inputLabel}>Laptop Server URL:</Text>
              <TextInput
                style={styles.modalInput}
                placeholder="e.g. https://your-ngrok.ngrok-free.app"
                placeholderTextColor="#666680"
                value={tempServerUrl}
                onChangeText={setTempServerUrl}
                autoCapitalize="none"
              />
              
              <View style={styles.modalButtons}>
                <TouchableOpacity
                  onPress={() => {
                    setTempServerUrl(serverUrl);
                    setShowSettings(false);
                  }}
                  style={[styles.modalButton, styles.cancelButton]}
                >
                  <Text style={styles.modalButtonText}>Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  onPress={handleSaveSettings}
                  style={[styles.modalButton, styles.saveButton]}
                >
                  <Text style={styles.modalButtonText}>Connect</Text>
                </TouchableOpacity>
              </View>
            </LinearGradient>
          </View>
        </Modal>

      </LinearGradient>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#080810',
  },
  gradient: {
    flex: 1,
  },
  header: {
    paddingHorizontal: 20,
    paddingVertical: 15,
    borderBottomWidth: 1,
    borderBottomColor: '#1A1A30',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '900',
    color: '#FFF',
    letterSpacing: 2,
  },
  statusContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 4,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  headerSubtitle: {
    fontSize: 12,
    color: '#666680',
    fontWeight: '600',
  },
  headerActions: {
    flexDirection: 'row',
  },
  headerButton: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: '#1C1C30',
    marginLeft: 8,
    borderWidth: 1,
    borderColor: '#303050',
  },
  headerButtonText: {
    fontSize: 12,
    color: '#FFF',
    fontWeight: 'bold',
  },
  messagesContainer: {
    padding: 15,
    paddingBottom: 25,
  },
  messageWrapper: {
    marginVertical: 6,
    flexDirection: 'row',
    width: '100%',
  },
  userWrapper: {
    justifyContent: 'flex-end',
  },
  kiraWrapper: {
    justifyContent: 'flex-start',
  },
  messageBubble: {
    maxWidth: '85%',
    padding: 12,
    borderRadius: 16,
    borderWidth: 1,
  },
  userBubble: {
    borderBottomRightRadius: 2,
    borderColor: '#4E2C7C',
  },
  kiraBubble: {
    borderBottomLeftRadius: 2,
    borderColor: '#303050',
  },
  loadingBubble: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  messageText: {
    fontSize: 15,
    color: '#FFF',
    lineHeight: 20,
  },
  messageTime: {
    fontSize: 10,
    color: '#666680',
    alignSelf: 'flex-end',
    marginTop: 4,
  },
  visualizerContainer: {
    height: 140,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
  },
  micButton: {
    width: 70,
    height: 70,
    borderRadius: 35,
    backgroundColor: '#1E1E36',
    borderWidth: 2,
    borderColor: '#00E5FF',
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 8,
    shadowColor: '#00E5FF',
    shadowOpacity: 0.3,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 0 },
    zIndex: 10,
  },
  micButtonActive: {
    backgroundColor: '#00E5FF',
    borderColor: '#FFF',
  },
  micIcon: {
    fontSize: 32,
    color: '#FFF',
  },
  micHelpText: {
    color: '#666680',
    fontSize: 13,
    fontWeight: '600',
    marginTop: 8,
  },
  pulseContainer: {
    position: 'absolute',
    alignItems: 'center',
    justifyContent: 'center',
  },
  pulseCircle: {
    position: 'absolute',
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: '#00E5FF',
  },
  inputContainer: {
    flexDirection: 'row',
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: '#1A1A30',
    backgroundColor: '#080810',
    alignItems: 'center',
  },
  textInput: {
    flex: 1,
    height: 44,
    backgroundColor: '#121224',
    borderRadius: 22,
    paddingHorizontal: 16,
    color: '#FFF',
    fontSize: 15,
    borderWidth: 1,
    borderColor: '#262646',
  },
  sendButton: {
    marginLeft: 10,
    paddingHorizontal: 18,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#5E2C9B',
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendButtonText: {
    color: '#FFF',
    fontSize: 15,
    fontWeight: 'bold',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalContent: {
    width: '100%',
    borderRadius: 20,
    padding: 25,
    borderWidth: 1,
    borderColor: '#303050',
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '900',
    color: '#FFF',
    marginBottom: 20,
    letterSpacing: 1.5,
  },
  inputLabel: {
    color: '#666680',
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 8,
  },
  modalInput: {
    backgroundColor: '#121224',
    borderWidth: 1,
    borderColor: '#262646',
    borderRadius: 10,
    height: 48,
    color: '#FFF',
    paddingHorizontal: 15,
    fontSize: 15,
    marginBottom: 20,
  },
  modalButtons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  modalButton: {
    flex: 1,
    height: 44,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cancelButton: {
    backgroundColor: '#1C1C30',
    marginRight: 10,
    borderWidth: 1,
    borderColor: '#303050',
  },
  saveButton: {
    backgroundColor: '#00E5FF',
    marginLeft: 10,
  },
  modalButtonText: {
    fontWeight: 'bold',
    fontSize: 15,
    color: '#FFF',
  },
});
