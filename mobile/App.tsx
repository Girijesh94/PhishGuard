import { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, FlatList, SafeAreaView, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as SecureStore from 'expo-secure-store';
import { StatusBar } from 'expo-status-bar';

type Feature = { feature: string; value?: number; contribution: number };
type Scan = {
  id: string; url: string; normalized_url: string; label: 'phishing' | 'legitimate';
  confidence: number; phishing_probability: number; top_features: Feature[];
  top_features_method: string; created_at: string;
};
const API_URL = process.env.EXPO_PUBLIC_API_URL?.replace(/\/$/, '');
const TOKEN_KEY = 'phishguard_jwt';

async function api(path: string, method: string, token?: string, body?: object) {
  if (!API_URL) throw new Error('Set EXPO_PUBLIC_API_URL to the Express server URL.');
  const response = await fetch(API_URL + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {})
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}

function Button({ title, onPress, secondary = false, disabled = false }: {
  title: string; onPress: () => void; secondary?: boolean; disabled?: boolean
}) {
  return <TouchableOpacity accessibilityRole="button" disabled={disabled} onPress={onPress}
    style={[styles.button, secondary && styles.secondary, disabled && styles.disabled]}>
    <Text style={[styles.buttonText, secondary && styles.secondaryText]}>{title}</Text>
  </TouchableOpacity>;
}

export default function App() {
  const [token, setToken] = useState<string | null>(null);
  const [loadingToken, setLoadingToken] = useState(true);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [view, setView] = useState<'scan' | 'history' | 'camera'>('scan');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [url, setUrl] = useState('');
  const [result, setResult] = useState<Scan | null>(null);
  const [history, setHistory] = useState<Scan[]>([]);
  const [permission, requestPermission] = useCameraPermissions();

  useEffect(() => {
    SecureStore.getItemAsync(TOKEN_KEY).then(setToken).catch(() => setToken(null))
      .finally(() => setLoadingToken(false));
  }, []);

  async function loadHistory(currentToken: string) {
    try {
      const data = await api('/api/scans', 'GET', currentToken);
      setHistory(data.scans);
    } catch (error) {
      if (String(error).includes('token') || String(error).includes('Authentication')) {
        await SecureStore.deleteItemAsync(TOKEN_KEY);
        setToken(null);
      } else Alert.alert('History unavailable', String(error));
    }
  }
  useEffect(() => { if (token) void loadHistory(token); }, [token]);

  async function authenticate() {
    setBusy(true);
    try {
      const data = await api('/api/auth/' + mode, 'POST', undefined, { email, password });
      await SecureStore.setItemAsync(TOKEN_KEY, data.token);
      setToken(data.token);
      setPassword('');
    } catch (error) { Alert.alert('Sign in failed', String(error)); }
    finally { setBusy(false); }
  }
  async function signOut() {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    setToken(null); setHistory([]); setResult(null); setView('scan');
  }
  async function scan() {
    if (!token || !url.trim()) return;
    setBusy(true);
    try {
      const data: Scan = await api('/api/scans', 'POST', token, { url: url.trim() });
      setResult(data);
      setHistory(previous => [data, ...previous]);
    } catch (error) { Alert.alert('Scan failed', String(error)); }
    finally { setBusy(false); }
  }
  async function showCamera() {
    if (!permission?.granted) {
      const requested = await requestPermission();
      if (!requested.granted) { Alert.alert('Camera permission needed', 'Allow camera access to scan QR codes.'); return; }
    }
    setView('camera');
  }

  if (loadingToken) return <SafeAreaView style={styles.center}><ActivityIndicator /></SafeAreaView>;
  return <SafeAreaView style={styles.screen}>
    <StatusBar style="light" />
    <View style={styles.header}>
      <Text style={styles.brand}>PHISHGUARD</Text>
      {token && <TouchableOpacity accessibilityRole="button" onPress={() => void signOut()}>
        <Text style={styles.headerLink}>Sign out</Text>
      </TouchableOpacity>}
    </View>
    {!token ? <ScrollView contentContainerStyle={styles.content}>
      <Text style={styles.heading}>Check links before you open them.</Text>
      <Text style={styles.subheading}>Sign in to scan and keep a private history.</Text>
      <TextInput style={styles.input} placeholder="Email" keyboardType="email-address"
        autoCapitalize="none" autoComplete="email" value={email} onChangeText={setEmail} />
      <TextInput style={styles.input} placeholder="Password" secureTextEntry
        autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
        value={password} onChangeText={setPassword} />
      <Button title={busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
        onPress={() => void authenticate()} disabled={busy} />
      <Button secondary title={mode === 'login' ? 'Create an account' : 'I have an account'}
        onPress={() => setMode(mode === 'login' ? 'register' : 'login')} />
      {!API_URL && <Text style={styles.note}>Set EXPO_PUBLIC_API_URL to your Express server address.</Text>}
    </ScrollView> : view === 'camera' ? <View style={styles.cameraPage}>
      <Text style={styles.cameraHint}>Point at a QR code containing a URL.</Text>
      <CameraView style={styles.camera} barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
        onBarcodeScanned={({ data }) => {
          setUrl(data); setResult(null); setView('scan');
        }} />
      <Button secondary title="Cancel" onPress={() => setView('scan')} />
    </View> : <>
      <View style={styles.tabs}>
        <TouchableOpacity accessibilityRole="button" onPress={() => setView('scan')}>
          <Text style={[styles.tab, view === 'scan' && styles.activeTab]}>Scan</Text>
        </TouchableOpacity>
        <TouchableOpacity accessibilityRole="button" onPress={() => { setView('history'); void loadHistory(token); }}>
          <Text style={[styles.tab, view === 'history' && styles.activeTab]}>History</Text>
        </TouchableOpacity>
      </View>
      {view === 'scan' ? <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.heading}>Is this link suspicious?</Text>
        <Text style={styles.subheading}>Paste a URL or scan a QR code. A prediction is only a signal, never a safety guarantee.</Text>
        <TextInput style={[styles.input, styles.urlInput]} placeholder="https://example.com"
          autoCapitalize="none" autoCorrect={false} keyboardType="url" value={url}
          onChangeText={text => { setUrl(text); setResult(null); }} />
        <Button title={busy ? 'Analyzing…' : 'Analyze URL'} onPress={() => void scan()} disabled={busy || !url.trim()} />
        <Button secondary title="Scan QR code" onPress={() => void showCamera()} />
        {result && <View style={styles.resultCard}>
          <Text style={[styles.verdict, result.label === 'phishing' ? styles.danger : styles.caution]}>
            {result.label === 'phishing' ? 'Likely phishing' : 'Looks legitimate'}
          </Text>
          <Text style={styles.metric}>Confidence: {Math.round(result.confidence * 100)}%</Text>
          <Text style={styles.metric}>Phishing score: {Math.round(result.phishing_probability * 100)}%</Text>
          <Text style={styles.note}>A low phishing score does not certify that a link is safe.</Text>
          <Text style={styles.sectionTitle}>Contributing URL patterns</Text>
          {result.top_features.map((item, index) =>
            <Text key={item.feature + index} style={styles.feature}>
              {item.feature}: {item.contribution > 0 ? '+' : ''}{item.contribution.toFixed(3)}
            </Text>)}
          <Text style={styles.note}>{result.top_features_method}</Text>
        </View>}
      </ScrollView> : <FlatList data={history} keyExtractor={item => item.id}
        contentContainerStyle={styles.content} ListEmptyComponent={<Text style={styles.note}>No scans yet.</Text>}
        renderItem={({ item }) => <View style={styles.historyCard}>
          <Text style={[styles.historyLabel, item.label === 'phishing' ? styles.danger : styles.caution]}>
            {item.label === 'phishing' ? 'Likely phishing' : 'Looks legitimate'} · {Math.round(item.confidence * 100)}%
          </Text>
          <Text selectable style={styles.historyUrl}>{item.url}</Text>
          <Text style={styles.note}>{new Date(item.created_at).toLocaleString()}</Text>
        </View>} />}
    </>}
  </SafeAreaView>;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#f7f9fb' },
  center: { flex: 1, justifyContent: 'center' },
  header: { backgroundColor: '#14233d', paddingHorizontal: 22, paddingVertical: 18,
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  brand: { color: '#fff', fontWeight: '800', letterSpacing: 2, fontSize: 18 },
  headerLink: { color: '#d6e6ff', fontSize: 14 },
  content: { padding: 22, gap: 12, paddingBottom: 40 },
  heading: { color: '#14233d', fontSize: 29, fontWeight: '800', marginTop: 20 },
  subheading: { color: '#52647e', fontSize: 15, lineHeight: 23, marginBottom: 12 },
  input: { borderWidth: 1, borderColor: '#c8d4e1', backgroundColor: '#fff',
    borderRadius: 12, paddingHorizontal: 16, paddingVertical: 14, fontSize: 16, color: '#14233d' },
  urlInput: { marginTop: 12 },
  button: { backgroundColor: '#2463eb', borderRadius: 12, alignItems: 'center', padding: 16, marginTop: 5 },
  buttonText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  secondary: { backgroundColor: '#e5edfa' },
  secondaryText: { color: '#1d4a98' },
  disabled: { opacity: 0.55 },
  note: { color: '#62718a', fontSize: 12, lineHeight: 18, marginTop: 8 },
  tabs: { flexDirection: 'row', paddingHorizontal: 22, paddingTop: 12, gap: 28, borderBottomWidth: 1, borderColor: '#dde4ee' },
  tab: { paddingBottom: 12, fontSize: 16, color: '#718098', fontWeight: '600' },
  activeTab: { color: '#2463eb', borderBottomWidth: 3, borderColor: '#2463eb' },
  resultCard: { backgroundColor: '#fff', borderRadius: 16, padding: 20, marginTop: 18, borderWidth: 1, borderColor: '#e1e8f0' },
  verdict: { fontSize: 23, fontWeight: '800', marginBottom: 8 },
  danger: { color: '#b42332' },
  caution: { color: '#08704e' },
  metric: { color: '#14233d', fontSize: 15, marginTop: 4 },
  sectionTitle: { fontWeight: '700', color: '#14233d', fontSize: 16, marginTop: 18 },
  feature: { fontSize: 13, color: '#44546d', marginTop: 5 },
  historyCard: { backgroundColor: '#fff', padding: 17, borderRadius: 12, marginBottom: 12,
    borderWidth: 1, borderColor: '#e1e8f0' },
  historyLabel: { fontWeight: '800', fontSize: 15 },
  historyUrl: { color: '#14233d', fontSize: 14, marginTop: 7 },
  cameraPage: { flex: 1, padding: 22 },
  cameraHint: { color: '#14233d', fontSize: 17, marginBottom: 12 },
  camera: { flex: 1, borderRadius: 12, overflow: 'hidden', marginBottom: 16 }
});
