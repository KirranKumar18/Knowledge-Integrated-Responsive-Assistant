import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = window.location.port === '5173' ? 'http://localhost:8000' : '';

export interface ProductivityData {
  current_distraction_time: number;
  distraction_threshold: number;
  status: 'productive' | 'distracted';
}

export const useProductivityData = () => {
  const [data, setData] = useState<ProductivityData>({
    current_distraction_time: 0,
    distraction_threshold: 300,
    status: 'productive',
  });

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const resp = await axios.get(`${API_BASE}/productivity`);
        setData(resp.data);
      } catch (err) {
        console.error('Failed to fetch productivity stats:', err);
      }
    };

    // Fetch immediately
    fetchStats();

    // Poll every 30 seconds
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, []);

  return data;
};
