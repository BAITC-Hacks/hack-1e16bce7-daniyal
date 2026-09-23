import { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';

const apiUrl = process.env.EXPO_PUBLIC_API_URL?.replace(/\/$/, '');

export default function App() {
  const [status, setStatus] = useState('Проверяем подключение…');
  useEffect(() => {
    if (!apiUrl) {
      setStatus('Подключение к сервису ещё не настроено.');
      return;
    }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    let active = true;
    fetch(`${apiUrl}/api/v1/ready`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error('Service unavailable');
        const data = await response.json();
        if (data.status !== 'ready' || data.database !== 'ok') throw new Error('Service not ready');
        if (active) setStatus('Сервис подключён и готов к работе');
      })
      .catch(() => { if (active) setStatus('Сервис временно недоступен. Попробуйте открыть приложение позже.'); })
      .finally(() => clearTimeout(timeout));
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, []);

  return (
    <View style={styles.screen}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={styles.content} contentInsetAdjustmentBehavior="automatic">
        <Text style={styles.brand}>CAREER QUEST</Text>
        <Text style={styles.eyebrow}>ВАША КАРЬЕРНАЯ ТРАЕКТОРИЯ</Text>
        <Text style={styles.title}>Каждый шаг — ближе к цели.</Text>
        <Text style={styles.intro}>Развивайте навыки и открывайте новые возможности для роста.</Text>
        <View style={styles.card}>
          <Text style={styles.heading}>Начало вашего пути</Text>
          <Text style={styles.body}>Скоро здесь появятся ваш профиль, рекомендации и прогресс по навыкам.</Text>
          <Text accessibilityLiveRegion="polite" style={styles.status}>{status}</Text>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#f3f7f4' },
  content: { paddingHorizontal: 24, paddingTop: 72, paddingBottom: 48 },
  brand: { fontSize: 14, fontWeight: '700', letterSpacing: 2, color: '#16392e' },
  eyebrow: { marginTop: 64, fontSize: 11, letterSpacing: 1, color: '#38634f' },
  title: { marginTop: 16, fontSize: 42, fontWeight: '700', letterSpacing: -1, color: '#16392e' },
  intro: { marginTop: 20, fontSize: 18, lineHeight: 28, color: '#38634f' },
  card: { marginTop: 40, padding: 24, borderRadius: 24, backgroundColor: '#fff', borderWidth: 1, borderColor: '#d7e4db' },
  heading: { fontSize: 21, fontWeight: '600', color: '#16392e' },
  body: { marginTop: 12, fontSize: 16, lineHeight: 25, color: '#38634f' },
  status: { marginTop: 24, fontSize: 14, lineHeight: 22, color: '#38634f' },
});
