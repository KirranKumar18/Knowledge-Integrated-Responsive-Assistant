import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = window.location.port === '5173' ? 'http://localhost:8000' : '';

export interface CalendarEvent {
  summary: string;
  start: string;
}

export interface CalendarData {
  events: CalendarEvent[];
}

export const useCalendarData = () => {
  const [data, setData] = useState<CalendarData>({
    events: [],
  });

  useEffect(() => {
    const fetchCalendar = async () => {
      try {
        const resp = await axios.get(`${API_BASE}/calendar`);
        setData(resp.data);
      } catch (err) {
        console.error('Failed to fetch calendar events:', err);
      }
    };

    // Fetch immediately
    fetchCalendar();

    // Poll every 5 minutes
    const interval = setInterval(fetchCalendar, 300000);
    return () => clearInterval(interval);
  }, []);

  return data;
};
