import React, { useState, useMemo, useEffect } from 'react';
import {
  Car, Users, Accessibility, Clock, MapPin,
  Brain, CircleCheck, CircleDot, CircleDashed, Coffee,
  Calendar, ShieldCheck,
  Loader2, AlertCircle, RefreshCw,
  Building2, UserCircle, Check, X, Bell, Phone,
  ChevronDown, Inbox, ArrowRight, MessageSquare
} from 'lucide-react';

// ─────────────────────────────────────────────────────────────────────
// API config — point at your MET Transport Service
// ─────────────────────────────────────────────────────────────────────

const API_BASE = '';                                 // e.g. 'http://localhost:8000' or 'https://api.carekiki.dev'
const DASHBOARD_ENDPOINT = '/transport/dashboard';   // GET ?role=admin|driver|escort[&id=...]
const MY_BOOKINGS_ENDPOINT = '/transport/dashboard'; // GET ?role=driver|escort&id={uuid}
const ACCEPT_ENDPOINT = '';                          // POST /{driver_id}/trips/{trip_id}/accept — within backend/driver/
const REJECT_ENDPOINT = '';                          // POST /{driver_id}/trips/{trip_id}/reject — within backend/driver/
const NOTIFY_ARRIVAL_ENDPOINT = '';                  // POST /{trip_id}/reaching { actor_id, actor_type } — not yet implemented
const PROVIDER_NAME = 'TOUCH Community Services';
const USE_MOCK_FALLBACK = true;                      // false → empty UI on API error

// ─────────────────────────────────────────────────────────────────────
// Mock data — used as initial state and as fallback when API is down.
// Backend response from POST /transport/dashboard should match this shape.
// ─────────────────────────────────────────────────────────────────────

const MOCK_PROVIDER = {
  name: 'TOUCH Community Services',
  id: 'MET · TCS',
  dateLabel: 'Monday, 11 May 2026',
  hours: 'Mon–Fri · 9am–6pm',
};

const MOCK_SERVICE_AREAS = [
  'Ang Mo Kio', 'Bishan', 'Sin Ming', 'Toa Payoh', 'Whampoa',
  'Bendemeer', 'Potong Pasir', 'Jurong', 'Boon Lay',
];

const MOCK_DRIVERS = [
  { id: 'd1', name: 'Lim Wei Ming',      vehicle: 'Toyota Hiace · WCA-1234',   wheelchair: true,  phone: '+65 9123 4567', area: 'Toa Payoh'   },
  { id: 'd2', name: 'Tan Boon Hock',     vehicle: 'Honda Odyssey · SGX-5678',  wheelchair: false, phone: '+65 9234 5678', area: 'Ang Mo Kio'  },
  { id: 'd3', name: 'Kumar Rajesh',      vehicle: 'Toyota Hiace · WCA-9012',   wheelchair: true,  phone: '+65 9345 6789', area: 'Boon Lay'    },
  { id: 'd4', name: 'Ahmad Bin Ismail',  vehicle: 'Toyota Vellfire · SGY-3456',wheelchair: false, phone: '+65 9456 7890', area: 'Whampoa'     },
  { id: 'd5', name: 'Chen Mei Lin',      vehicle: 'Hyundai Staria · WCA-7890', wheelchair: true,  phone: '+65 9567 8901', area: 'Bishan'      },
];

const MOCK_ESCORTS = [
  { id: 'e1', name: 'Siti Nurhaliza', languages: ['English', 'Malay'],                dementia: true,  phone: '+65 9678 9012', area: 'Toa Payoh'   },
  { id: 'e2', name: 'Mary Tan',       languages: ['English', 'Mandarin', 'Hokkien'],  dementia: false, phone: '+65 9789 0123', area: 'Ang Mo Kio'  },
  { id: 'e3', name: 'Priya Devi',     languages: ['English', 'Tamil', 'Hindi'],       dementia: false, phone: '+65 9890 1234', area: 'Boon Lay'    },
  { id: 'e4', name: 'Lee Hui Min',    languages: ['English', 'Mandarin'],             dementia: true,  phone: '+65 9901 2345', area: 'Bishan'      },
  { id: 'e5', name: 'Farah Aziz',     languages: ['English', 'Malay'],                dementia: false, phone: '+65 9012 3456', area: 'Whampoa'     },
];

const MOCK_TRIPS = [
  {
    id: 't1', elderly: 'Mdm Lim Choo Neo', age: 82, accessibility: 'wheelchair',
    pickup: { time: '09:00', location: 'Blk 123 Toa Payoh Lor 1' },
    appointment: { time: '09:45', location: 'Singapore General Hospital', clinic: 'Geriatric Clinic' },
    returnTime: '12:00',
    driverId: 'd1', escortId: 'e1', status: 'completed',
    subsidy: 'SMF · 50% subsidy',
    caregiver: 'Mr Lim Boon Heng', caregiverPhone: '+65 8123 4567',
    notes: null,
  },
  {
    id: 't2', elderly: 'Mr Goh Tian Seng', age: 76, accessibility: 'ambulant',
    pickup: { time: '09:30', location: 'Blk 456 Ang Mo Kio Ave 10' },
    appointment: { time: '10:30', location: 'National University Hospital', clinic: 'Cardiology' },
    returnTime: '12:30',
    driverId: 'd2', escortId: 'e2', status: 'in-progress',
    subsidy: 'PG · 75% subsidy',
    caregiver: 'Ms Goh Mei Ling', caregiverPhone: '+65 8234 5678',
    notes: null,
  },
  {
    id: 't3', elderly: 'Mdm Wong Ah Lan', age: 88, accessibility: 'wheelchair',
    pickup: { time: '11:00', location: 'Blk 234 Bishan St 22' },
    appointment: { time: '12:00', location: 'Changi General Hospital', clinic: 'Memory Clinic' },
    returnTime: '14:30',
    driverId: 'd5', escortId: 'e4', status: 'upcoming',
    subsidy: 'PG · 75% subsidy',
    caregiver: 'Mdm Wong Su Yin', caregiverPhone: '+65 8345 6789',
    notes: 'Dementia diagnosis — escort with dementia training assigned',
  },
  {
    id: 't4', elderly: 'Mdm Ng Siew Hua', age: 85, accessibility: 'wheelchair',
    pickup: { time: '13:30', location: 'Blk 678 Boon Lay Dr' },
    appointment: { time: '14:30', location: 'KK Women\u2019s & Children\u2019s Hospital', clinic: 'Orthopaedics' },
    returnTime: '17:00',
    driverId: 'd3', escortId: 'e3', status: 'upcoming',
    subsidy: 'SMF · 50% subsidy',
    caregiver: 'Ms Ng Pei Shan', caregiverPhone: '+65 8456 7890',
    notes: null,
  },
  {
    id: 't5', elderly: 'Mr Rashid Bin Omar', age: 79, accessibility: 'ambulant',
    pickup: { time: '14:30', location: 'Blk 89 Whampoa Dr' },
    appointment: { time: '15:30', location: 'Khoo Teck Puat Hospital', clinic: 'Renal Clinic' },
    returnTime: '17:30',
    driverId: 'd4', escortId: 'e5', status: 'upcoming',
    subsidy: 'Self-pay',
    caregiver: 'Mr Rashid Junior', caregiverPhone: '+65 8567 8901',
    notes: null,
  },
];

// Pending requests — trips matched by MET Transport but awaiting driver/escort accept.
// The same trip object lands in BOTH the driver's and the escort's pending list.
const MOCK_PENDING = [
  {
    id: 'p1', elderly: 'Mdm Tan Soo Kheng', age: 84, accessibility: 'wheelchair',
    pickup: { time: '09:00', location: 'Blk 167 Toa Payoh Lor 1', date: 'Tue, 12 May' },
    appointment: { time: '10:00', location: 'Tan Tock Seng Hospital', clinic: 'Cardiology' },
    returnTime: '12:30',
    driverId: 'd1', escortId: 'e1', status: 'pending',
    subsidy: 'PG · 75% subsidy',
    caregiver: 'Ms Tan Li Yuan', caregiverPhone: '+65 8678 1234',
    notes: null,
    matchScore: 94, matchReasons: ['Same area: Toa Payoh', 'WCA-equipped vehicle', 'Schedule available'],
  },
  {
    id: 'p2', elderly: 'Mr Heng Beng Choo', age: 77, accessibility: 'ambulant',
    pickup: { time: '13:30', location: 'Blk 88 Toa Payoh Central', date: 'Tue, 12 May' },
    appointment: { time: '14:30', location: 'Singapore General Hospital', clinic: 'Diabetes Centre' },
    returnTime: '17:00',
    driverId: 'd1', escortId: 'e2', status: 'pending',
    subsidy: 'SMF · 50% subsidy',
    caregiver: 'Mdm Heng Lai Peng', caregiverPhone: '+65 8789 2345',
    notes: null,
    matchScore: 82, matchReasons: ['Same area: Toa Payoh', 'Schedule available', 'Sedan acceptable for ambulant patient'],
  },
  {
    id: 'p3', elderly: 'Mdm Lim Geok Hua', age: 81, accessibility: 'ambulant',
    pickup: { time: '10:30', location: 'Blk 502 Ang Mo Kio Ave 5', date: 'Tue, 12 May' },
    appointment: { time: '11:30', location: 'Mount Alvernia Hospital', clinic: 'Endocrinology' },
    returnTime: '14:00',
    driverId: 'd2', escortId: 'e2', status: 'pending',
    subsidy: 'Self-pay',
    caregiver: 'Mr Lim Wei Liang', caregiverPhone: '+65 8890 3456',
    notes: null,
    matchScore: 88, matchReasons: ['Same area: Ang Mo Kio', 'Schedule available'],
  },
  {
    id: 'p4', elderly: 'Mr Krishnan s/o Raman', age: 73, accessibility: 'wheelchair',
    pickup: { time: '08:30', location: 'Blk 215 Boon Lay Pl', date: 'Tue, 12 May' },
    appointment: { time: '09:30', location: 'National University Hospital', clinic: 'Nephrology' },
    returnTime: '12:00',
    driverId: 'd3', escortId: 'e3', status: 'pending',
    subsidy: 'PG · 75% subsidy',
    caregiver: 'Ms Anitha Krishnan', caregiverPhone: '+65 8901 4567',
    notes: 'Fortnightly dialysis — patient knows the routine',
    matchScore: 91, matchReasons: ['Same area: Boon Lay', 'WCA-equipped vehicle', 'Tamil-speaking escort'],
  },
  {
    id: 'p5', elderly: 'Mdm Chua Bee Geok', age: 86, accessibility: 'wheelchair',
    pickup: { time: '14:00', location: 'Blk 174 Bishan St 13', date: 'Tue, 12 May' },
    appointment: { time: '15:00', location: 'Mount Elizabeth Novena Hospital', clinic: 'Memory Clinic' },
    returnTime: '17:30',
    driverId: 'd5', escortId: 'e4', status: 'pending',
    subsidy: 'PG · 75% subsidy',
    caregiver: 'Ms Chua Hui Min', caregiverPhone: '+65 9012 5678',
    notes: 'Dementia diagnosis — escort with dementia training preferred',
    matchScore: 96, matchReasons: ['Same area: Bishan', 'WCA-equipped vehicle', 'Dementia-trained escort'],
  },
];

// Replacement match returned after a reject — used in mock fallback.
const MOCK_REPLACEMENT_MATCH = {
  id: 'p99', elderly: 'Mr Yeo Kian Seng', age: 79, accessibility: 'ambulant',
  pickup: { time: '11:00', location: 'Blk 132 Toa Payoh Lor 1', date: 'Tue, 12 May' },
  appointment: { time: '12:00', location: 'Raffles Hospital', clinic: 'Orthopaedics' },
  returnTime: '14:30',
  driverId: 'd1', escortId: 'e1', status: 'pending',
  subsidy: 'Self-pay',
  caregiver: 'Mr Yeo Wei Jian', caregiverPhone: '+65 9123 6789',
  notes: null,
  matchScore: 78, matchReasons: ['Same area: Toa Payoh', 'Schedule available'],
};

// ─────────────────────────────────────────────────────────────────────
// Time math
// ─────────────────────────────────────────────────────────────────────

const HOUR_START = 9;
const HOUR_END = 18;
const HOURS = HOUR_END - HOUR_START; // 12
const PX_PER_HOUR = 96;
const TIMELINE_WIDTH = HOURS * PX_PER_HOUR; // 1152

const timeToPx = (t) => {
  const [h, m] = t.split(':').map(Number);
  return Math.max(0, ((h - HOUR_START) + m / 60) * PX_PER_HOUR);
};

// ─────────────────────────────────────────────────────────────────────
// Status visuals
// ─────────────────────────────────────────────────────────────────────

const STATUS_STYLES = {
  'completed':   { label: 'Completed',   bg: '#1F5F4F', border: '#0E3D31', text: '#F4F1E8', accent: '#7FCBA9', Icon: CircleCheck },
  'in-progress': { label: 'In progress', bg: '#C9622A', border: '#8C3F14', text: '#FDF7E8', accent: '#F4A464', Icon: CircleDot   },
  'upcoming':    { label: 'Upcoming',    bg: '#2B3A55', border: '#0F1B30', text: '#F1F0EA', accent: '#7E9DD0', Icon: CircleDashed },
  'pending':     { label: 'Pending',     bg: '#7B5BA6', border: '#4D3873', text: '#F5F0FA', accent: '#C9B3E0', Icon: Inbox       },
};

// ─────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────

export default function CarekikiDashboard() {
  const [view, setView] = useState('admin'); // 'admin' | 'driver-escort'
  const [toast, setToast] = useState(null);
  const [selectedTripId, setSelectedTripId] = useState('t2');
  const [activeTab, setActiveTab] = useState('drivers');
  const [selectedArea, setSelectedArea] = useState('all');

  // Live data from /transport/dashboard, falls back to MOCK_* on error
  const [provider, setProvider]         = useState(MOCK_PROVIDER);
  const [serviceAreas, setServiceAreas] = useState(MOCK_SERVICE_AREAS);
  const [drivers, setDrivers]           = useState(MOCK_DRIVERS);
  const [escorts, setEscorts]           = useState(MOCK_ESCORTS);
  const [trips, setTrips]               = useState(MOCK_TRIPS);
  const [apiState, setApiState]         = useState({ status: 'idle', error: null, lastSync: null });

  const fetchDashboard = async () => {
    setApiState({ status: 'loading', error: null, lastSync: null });
    try {
      // GET /transport/dashboard?role=admin
      const res = await fetch(`${API_BASE}${DASHBOARD_ENDPOINT}?role=admin`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      // Backend response shape: { drivers, escorts, past_trips, upcoming_trips }
      if (data.drivers)        setDrivers(data.drivers);
      if (data.escorts)        setEscorts(data.escorts);
      if (data.past_trips || data.upcoming_trips) {
        setTrips([...(data.past_trips || []), ...(data.upcoming_trips || [])]);
      }
      const now = new Date();
      const hh = String(now.getHours()).padStart(2,'0');
      const mm = String(now.getMinutes()).padStart(2,'0');
      setApiState({ status: 'live', error: null, lastSync: `${hh}:${mm}` });
    } catch (err) {
      console.error('[carekiki] dashboard fetch failed:', err);
      if (!USE_MOCK_FALLBACK) {
        setDrivers([]); setEscorts([]); setTrips([]);
      }
      setApiState({ status: 'error', error: err.message, lastSync: null });
    }
  };

  useEffect(() => { fetchDashboard(); }, []);

  const filteredDrivers = useMemo(
    () => drivers.filter(d =>
      selectedArea === 'all' ||
      (d.service_areas || []).includes(selectedArea) ||
      d.area === selectedArea
    ),
    [drivers, selectedArea]
  );
  const filteredEscorts = useMemo(
    () => escorts.filter(e =>
      selectedArea === 'all' ||
      (e.service_areas || []).includes(selectedArea) ||
      e.area === selectedArea
    ),
    [escorts, selectedArea]
  );

  const byDriverId = useMemo(() => {
    const m = {};
    trips.forEach(t => {
      if (t.driver_id) m[t.driver_id] = t;
      if (t.driverId)  m[t.driverId]  = t;
    });
    return m;
  }, [trips]);

  const byEscortId = useMemo(() => {
    const m = {};
    trips.forEach(t => {
      if (t.escort_id) m[t.escort_id] = t;
      if (t.escortId)  m[t.escortId]  = t;
    });
    return m;
  }, [trips]);

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300..700&family=Manrope:wght@300..800&family=JetBrains+Mono:wght@400..600&display=swap');

        .ck-root {
          --ck-bg:        #F4F1E8;
          --ck-bg-2:      #ECE7D7;
          --ck-surface:   #FBF9F2;
          --ck-ink:       #1B1A15;
          --ck-ink-2:     #4A463B;
          --ck-ink-3:     #7D7766;
          --ck-line:      #D9D2BD;
          --ck-line-2:    #C5BCA0;
          --ck-primary:   #1F5F4F;
          --ck-primary-2: #134236;
          --ck-amber:     #C9622A;
          --ck-blue:      #2B3A55;
          --ck-rose:      #B14651;

          font-family: 'Manrope', system-ui, sans-serif;
          color: var(--ck-ink);
          background: var(--ck-bg);
          background-image:
            radial-gradient(1200px 600px at 0% -10%, rgba(31,95,79,0.08), transparent 60%),
            radial-gradient(900px 500px at 110% 110%, rgba(201,98,42,0.06), transparent 55%);
          min-height: 100vh;
        }
        .ck-display { font-family: 'Fraunces', 'Times New Roman', serif; font-feature-settings: "ss01"; letter-spacing: -0.01em; }
        .ck-mono    { font-family: 'JetBrains Mono', ui-monospace, monospace; }

        .ck-card {
          background: var(--ck-surface);
          border: 1px solid var(--ck-line);
          border-radius: 14px;
          box-shadow: 0 1px 0 rgba(27,26,21,0.02), 0 6px 24px -16px rgba(27,26,21,0.10);
        }

        .ck-tag {
          display: inline-flex; align-items: center; gap: 6px;
          padding: 3px 9px; border-radius: 999px;
          font-size: 11px; font-weight: 600; letter-spacing: 0.02em;
          background: var(--ck-bg-2); color: var(--ck-ink-2);
          border: 1px solid var(--ck-line);
        }

        .ck-grid-line { background: linear-gradient(to right, transparent, var(--ck-line) 50%, transparent); }

        .ck-trip-block {
          position: absolute; top: 10px; bottom: 10px;
          border-radius: 10px;
          padding: 10px 12px;
          cursor: pointer;
          transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease;
          overflow: hidden;
          display: flex; flex-direction: column; justify-content: space-between;
          box-shadow: 0 2px 0 rgba(0,0,0,0.06), 0 8px 20px -12px rgba(0,0,0,0.30);
        }
        .ck-trip-block:hover { transform: translateY(-1px); filter: brightness(1.04); }
        .ck-trip-block.selected { outline: 2px solid var(--ck-ink); outline-offset: 2px; }
        .ck-trip-block .name { font-weight: 700; font-size: 13px; line-height: 1.2; }
        .ck-trip-block .meta { font-size: 11px; opacity: 0.85; }
        .ck-trip-block .accent-bar { position: absolute; left: 0; top: 0; bottom: 0; width: 4px; }

        .ck-now-line {
          position: absolute; top: -6px; bottom: -6px; width: 2px;
          background: var(--ck-rose);
        }
        .ck-now-line::before {
          content: ''; position: absolute; top: -6px; left: -5px;
          width: 12px; height: 12px; border-radius: 50%;
          background: var(--ck-rose); box-shadow: 0 0 0 4px rgba(177,70,81,0.18);
        }
        .ck-now-line::after {
          content: 'NOW'; position: absolute; top: -22px; left: 50%; transform: translateX(-50%);
          font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 600;
          color: var(--ck-rose); letter-spacing: 0.1em;
        }

        .ck-empty-slot {
          position: absolute; top: 14px; bottom: 14px;
          border: 1px dashed var(--ck-line-2);
          border-radius: 8px;
          background: repeating-linear-gradient(
            -45deg,
            transparent, transparent 6px,
            rgba(125,119,102,0.06) 6px, rgba(125,119,102,0.06) 12px
          );
          display: flex; align-items: center; justify-content: center;
          font-size: 10px; color: var(--ck-ink-3); font-weight: 600;
          letter-spacing: 0.12em; text-transform: uppercase;
        }

        .ck-row-divider {
          height: 1px;
          background: linear-gradient(to right, transparent, var(--ck-line) 8%, var(--ck-line) 92%, transparent);
        }

        .ck-section-header {
          display: flex; align-items: center; gap: 10px;
          padding: 14px 18px;
          background: linear-gradient(180deg, var(--ck-bg-2), transparent);
          font-size: 11px; font-weight: 700; letter-spacing: 0.18em; text-transform: uppercase;
          color: var(--ck-ink-2);
          border-bottom: 1px solid var(--ck-line);
        }

        .ck-tab-bar {
          display: flex; align-items: center; gap: 4px;
          padding: 10px 14px;
          background: linear-gradient(180deg, var(--ck-bg-2), transparent);
          border-bottom: 1px solid var(--ck-line);
        }
        .ck-tab {
          display: inline-flex; align-items: center; gap: 8px;
          padding: 8px 14px;
          border-radius: 8px;
          font-size: 12px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
          color: var(--ck-ink-3);
          background: transparent;
          border: 1px solid transparent;
          cursor: pointer;
          transition: all 0.15s ease;
        }
        .ck-tab:hover { color: var(--ck-ink-2); background: rgba(255,255,255,0.5); }
        .ck-tab.active {
          color: var(--ck-surface);
          background: var(--ck-ink);
          border-color: var(--ck-ink);
        }
        .ck-tab .count {
          font-family: 'JetBrains Mono', ui-monospace, monospace;
          font-size: 11px;
          padding: 2px 7px;
          border-radius: 999px;
          background: rgba(125,119,102,0.18);
          color: inherit;
          letter-spacing: 0;
        }
        .ck-tab.active .count {
          background: rgba(255,255,255,0.18);
        }

        .ck-filter-bar {
          display: flex; align-items: center; gap: 4px;
          padding: 8px 18px;
          background: var(--ck-bg);
          border-bottom: 1px solid var(--ck-line);
          flex-wrap: wrap;
        }
        .ck-filter-label {
          font-size: 10px; font-weight: 700; letter-spacing: 0.18em; text-transform: uppercase;
          color: var(--ck-ink-3);
          margin-right: 8px;
        }
        .ck-area-pill {
          display: inline-flex; align-items: center; gap: 5px;
          padding: 5px 11px;
          border-radius: 6px;
          font-size: 11px; font-weight: 600;
          color: var(--ck-ink-3);
          background: transparent;
          border: 1px solid transparent;
          cursor: pointer;
          transition: all 0.15s ease;
          white-space: nowrap;
        }
        .ck-area-pill:hover { color: var(--ck-ink-2); background: rgba(251,249,242,0.7); }
        .ck-area-pill.active {
          color: var(--ck-primary-2);
          background: #E6EFE8;
          border-color: #C4DACA;
        }

        .ck-status-pill {
          display: inline-flex; align-items: center; gap: 6px;
          padding: 4px 10px; border-radius: 999px;
          font-size: 11px; font-weight: 700; letter-spacing: 0.04em;
        }

        @keyframes ck-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.55; }
        }
        .ck-pulse { animation: ck-pulse 1.8s ease-in-out infinite; }

        .ck-scroll::-webkit-scrollbar { height: 8px; }
        .ck-scroll::-webkit-scrollbar-track { background: transparent; }
        .ck-scroll::-webkit-scrollbar-thumb { background: var(--ck-line-2); border-radius: 999px; }

        /* ─── View switcher ─── */
        .ck-view-switcher {
          display: inline-flex; gap: 4px;
          padding: 4px;
          background: var(--ck-bg-2);
          border: 1px solid var(--ck-line);
          border-radius: 12px;
          margin-bottom: 28px;
        }
        .ck-view-tab {
          display: inline-flex; align-items: center; gap: 8px;
          padding: 10px 18px;
          border-radius: 8px;
          font-size: 13px; font-weight: 700; letter-spacing: 0.02em;
          color: var(--ck-ink-3);
          background: transparent;
          border: none;
          cursor: pointer;
          transition: all 0.18s ease;
        }
        .ck-view-tab:hover { color: var(--ck-ink); }
        .ck-view-tab.active {
          color: var(--ck-surface);
          background: var(--ck-ink);
          box-shadow: 0 2px 8px -2px rgba(27,26,21,0.3);
        }

        /* ─── Identity selector ─── */
        .ck-identity-card {
          background: var(--ck-surface);
          border: 1px solid var(--ck-line);
          border-radius: 14px;
          padding: 18px 22px;
          display: flex; align-items: center; justify-content: space-between;
          gap: 20px;
          box-shadow: 0 1px 0 rgba(27,26,21,0.02), 0 6px 24px -16px rgba(27,26,21,0.10);
        }
        .ck-identity-avatar {
          width: 52px; height: 52px;
          border-radius: 50%;
          display: flex; align-items: center; justify-content: center;
          font-family: 'Fraunces', serif;
          font-size: 22px; font-weight: 500;
          background: var(--ck-primary);
          color: var(--ck-surface);
          flex-shrink: 0;
        }
        .ck-identity-select {
          appearance: none;
          padding: 10px 36px 10px 14px;
          border-radius: 8px;
          background: var(--ck-bg-2);
          border: 1px solid var(--ck-line);
          font-family: 'Manrope', sans-serif;
          font-size: 13px; font-weight: 600;
          color: var(--ck-ink);
          cursor: pointer;
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%237D7766' stroke-width='2.5'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
          background-repeat: no-repeat;
          background-position: right 12px center;
        }

        /* ─── Pending request card ─── */
        .ck-request-card {
          background: var(--ck-surface);
          border: 1px solid var(--ck-line);
          border-radius: 14px;
          overflow: hidden;
          box-shadow: 0 1px 0 rgba(27,26,21,0.02), 0 6px 24px -16px rgba(27,26,21,0.10);
        }
        .ck-request-card .header {
          padding: 14px 20px;
          background: linear-gradient(180deg, #F5F0FA, transparent);
          border-bottom: 1px solid var(--ck-line);
          display: flex; align-items: center; justify-content: space-between;
        }
        .ck-match-score {
          display: inline-flex; align-items: center; gap: 5px;
          padding: 4px 10px;
          border-radius: 999px;
          background: #E6EFE8;
          color: var(--ck-primary-2);
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px; font-weight: 700;
        }

        /* ─── Action buttons ─── */
        .ck-action-btn {
          flex: 1;
          padding: 14px 18px;
          border-radius: 10px;
          font-size: 14px; font-weight: 700; letter-spacing: 0.02em;
          display: inline-flex; align-items: center; justify-content: center; gap: 8px;
          cursor: pointer;
          transition: all 0.15s ease;
          border: 1px solid transparent;
        }
        .ck-action-accept {
          background: var(--ck-primary);
          color: var(--ck-surface);
          border-color: var(--ck-primary-2);
        }
        .ck-action-accept:hover { background: var(--ck-primary-2); transform: translateY(-1px); }
        .ck-action-reject {
          background: var(--ck-surface);
          color: var(--ck-rose);
          border-color: var(--ck-line-2);
        }
        .ck-action-reject:hover { background: #FBEEEF; border-color: var(--ck-rose); }
        .ck-action-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

        .ck-notify-btn {
          width: 100%;
          padding: 18px 24px;
          border-radius: 12px;
          font-size: 16px; font-weight: 700;
          letter-spacing: 0.02em;
          display: inline-flex; align-items: center; justify-content: center; gap: 10px;
          cursor: pointer;
          transition: all 0.15s ease;
          background: var(--ck-amber);
          color: var(--ck-surface);
          border: 1px solid #8C3F14;
          box-shadow: 0 2px 0 #8C3F14, 0 8px 20px -8px rgba(201,98,42,0.5);
        }
        .ck-notify-btn:hover { transform: translateY(-1px); box-shadow: 0 3px 0 #8C3F14, 0 10px 24px -8px rgba(201,98,42,0.6); }
        .ck-notify-btn:disabled {
          background: var(--ck-bg-2); color: var(--ck-ink-3);
          border-color: var(--ck-line); box-shadow: none;
          cursor: not-allowed; transform: none;
        }

        /* ─── Modal ─── */
        @keyframes ck-fade-in { from { opacity: 0; } to { opacity: 1; } }
        @keyframes ck-pop-in { from { opacity: 0; transform: scale(0.96) translateY(8px); } to { opacity: 1; transform: scale(1) translateY(0); } }
        .ck-modal-backdrop {
          position: fixed; inset: 0;
          background: rgba(27,26,21,0.45);
          backdrop-filter: blur(4px);
          z-index: 50;
          display: flex; align-items: center; justify-content: center;
          padding: 20px;
          animation: ck-fade-in 0.2s ease;
        }
        .ck-modal {
          background: var(--ck-surface);
          border-radius: 16px;
          width: 100%;
          max-width: 480px;
          max-height: 90vh;
          overflow-y: auto;
          border: 1px solid var(--ck-line);
          box-shadow: 0 20px 60px -20px rgba(0,0,0,0.4);
          animation: ck-pop-in 0.22s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .ck-textarea {
          width: 100%;
          padding: 12px 14px;
          border-radius: 10px;
          border: 1px solid var(--ck-line);
          background: var(--ck-bg);
          font-family: 'Manrope', sans-serif;
          font-size: 13px;
          color: var(--ck-ink);
          resize: vertical;
          min-height: 80px;
          transition: border-color 0.15s ease;
        }
        .ck-textarea:focus { outline: none; border-color: var(--ck-primary); }

        .ck-radio-row {
          display: flex; align-items: center; gap: 10px;
          padding: 10px 12px;
          border-radius: 8px;
          border: 1px solid var(--ck-line);
          cursor: pointer;
          transition: all 0.12s ease;
        }
        .ck-radio-row:hover { background: var(--ck-bg-2); }
        .ck-radio-row.selected {
          border-color: var(--ck-primary);
          background: #E6EFE8;
        }
        .ck-radio-dot {
          width: 16px; height: 16px;
          border-radius: 50%;
          border: 2px solid var(--ck-line-2);
          flex-shrink: 0;
          position: relative;
        }
        .ck-radio-row.selected .ck-radio-dot {
          border-color: var(--ck-primary);
        }
        .ck-radio-row.selected .ck-radio-dot::after {
          content: '';
          position: absolute; inset: 2px;
          border-radius: 50%;
          background: var(--ck-primary);
        }

        /* ─── Toast ─── */
        @keyframes ck-toast-in {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .ck-toast {
          position: fixed;
          bottom: 28px; left: 50%; transform: translateX(-50%);
          padding: 14px 22px;
          background: var(--ck-ink);
          color: var(--ck-surface);
          border-radius: 12px;
          font-size: 13px; font-weight: 600;
          display: flex; align-items: center; gap: 10px;
          box-shadow: 0 8px 24px -8px rgba(0,0,0,0.3);
          z-index: 60;
          animation: ck-toast-in 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        }
      `}</style>

      <div className="ck-root">
        <div className="max-w-[1400px] mx-auto px-8 py-8">

          {/* ─── VIEW SWITCHER ─── */}
          <div className="ck-view-switcher">
            <button
              className={`ck-view-tab ${view === 'admin' ? 'active' : ''}`}
              onClick={() => setView('admin')}
            >
              <Building2 size={16}/> Admin Dashboard
            </button>
            <button
              className={`ck-view-tab ${view === 'driver-escort' ? 'active' : ''}`}
              onClick={() => setView('driver-escort')}
            >
              <UserCircle size={16}/> Driver / Escort
            </button>
          </div>

          {view === 'driver-escort' && (
            <DriverEscortView
              drivers={drivers}
              escorts={escorts}
              trips={trips}
              showToast={(msg) => { setToast(msg); setTimeout(() => setToast(null), 2800); }}
            />
          )}

          {view === 'admin' && (<>

          {/* ─── HEADER ─── */}
          <header className="flex items-end justify-between mb-8 pb-6" style={{borderBottom: '1px solid var(--ck-line)'}}>
            <div>
              <h1 className="ck-display text-[40px] leading-tight font-medium" style={{color: 'var(--ck-ink)'}}>
                {provider.name}
              </h1>
              <div className="flex items-center gap-3 mt-2 text-sm flex-wrap" style={{color: 'var(--ck-ink-3)'}}>
                <span className="ck-mono">{provider.id}</span>
                <span>·</span>
                <span className="flex items-center gap-1.5"><Calendar size={13}/> {provider.dateLabel}</span>
                <span>·</span>
                <span className="flex items-center gap-1.5"><Clock size={13}/> {provider.hours}</span>
              </div>
              <div className="mt-4 max-w-[760px]">
                <div className="text-[10px] font-bold uppercase tracking-[0.18em] mb-2" style={{color: 'var(--ck-ink-3)'}}>
                  Service Areas
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <button
                    className={`ck-area-pill ${selectedArea === 'all' ? 'active' : ''}`}
                    onClick={() => setSelectedArea('all')}
                  >
                    All areas
                  </button>
                  {serviceAreas.map(a => (
                    <button
                      key={a}
                      className={`ck-area-pill ${selectedArea === a ? 'active' : ''}`}
                      onClick={() => setSelectedArea(a)}
                    >
                      <MapPin size={10}/> {a}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <ApiStatus apiState={apiState} onRefresh={fetchDashboard}/>
          </header>

          {/* ─── TIMELINE ─── */}
          <div className="ck-card mb-8 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-5" style={{borderBottom: '1px solid var(--ck-line)'}}>
              <div>
                <div className="text-[11px] font-bold uppercase tracking-[0.18em] mb-1" style={{color: 'var(--ck-ink-3)'}}>Schedule</div>
                <h2 className="ck-display text-[24px] font-medium">Today at a glance</h2>
              </div>
              <div className="flex items-center gap-4 text-xs" style={{color: 'var(--ck-ink-2)'}}>
                <LegendDot color={STATUS_STYLES.completed.bg} label="Completed"/>
                <LegendDot color={STATUS_STYLES['in-progress'].bg} label="In progress"/>
                <LegendDot color={STATUS_STYLES.upcoming.bg} label="Upcoming"/>
              </div>
            </div>

            <div className="overflow-x-auto ck-scroll">
              <div style={{minWidth: TIMELINE_WIDTH + 220}}>
                {/* hour axis */}
                <div className="flex" style={{paddingLeft: 220, borderBottom: '1px solid var(--ck-line)'}}>
                  <div className="relative" style={{width: TIMELINE_WIDTH, height: 44}}>
                    {Array.from({length: HOURS + 1}).map((_, i) => {
                      const hour = HOUR_START + i;
                      return (
                        <div key={i}
                          className="absolute top-0 bottom-0 flex items-end pb-2"
                          style={{left: i * PX_PER_HOUR, width: 1}}>
                          <div className="absolute top-0 bottom-0 w-px" style={{background: 'var(--ck-line)', left: 0}}/>
                          <div className="ck-mono text-[11px] font-semibold absolute"
                               style={{left: 6, bottom: 6, color: 'var(--ck-ink-3)'}}>
                            {String(hour).padStart(2,'0')}:00
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* TAB BAR */}
                <div className="ck-tab-bar">
                  <TabButton
                    active={activeTab === 'drivers'}
                    onClick={() => setActiveTab('drivers')}
                    icon={Car}
                    label="Drivers"
                    total={filteredDrivers.length}
                    onDuty={filteredDrivers.filter(d => byDriverId[d.id]).length}
                  />
                  <TabButton
                    active={activeTab === 'escorts'}
                    onClick={() => setActiveTab('escorts')}
                    icon={Users}
                    label="Escorts"
                    total={filteredEscorts.length}
                    onDuty={filteredEscorts.filter(e => byEscortId[e.id]).length}
                  />
                </div>

                {/* CONDITIONAL ROWS */}
                {activeTab === 'drivers' && (
                  filteredDrivers.length === 0
                    ? <EmptyState area={selectedArea} type="drivers"/>
                    : filteredDrivers.map((d, idx) => (
                        <ResourceRow
                          key={d.id}
                          resource={d}
                          type="driver"
                          trip={byDriverId[d.id]}
                          selectedTripId={selectedTripId}
                          onSelect={setSelectedTripId}
                          isLast={idx === filteredDrivers.length - 1}
                        />
                      ))
                )}

                {activeTab === 'escorts' && (
                  filteredEscorts.length === 0
                    ? <EmptyState area={selectedArea} type="escorts"/>
                    : filteredEscorts.map((e, idx) => (
                        <ResourceRow
                          key={e.id}
                          resource={e}
                          type="escort"
                          trip={byEscortId[e.id]}
                          selectedTripId={selectedTripId}
                          onSelect={setSelectedTripId}
                          isLast={idx === filteredEscorts.length - 1}
                        />
                      ))
                )}
              </div>
            </div>
          </div>

          {/* ─── FOOTER ─── */}
          <footer className="mt-10 pt-6 flex items-center justify-between text-xs" style={{borderTop: '1px solid var(--ck-line)', color: 'var(--ck-ink-3)'}}>
            <div className="flex items-center gap-2">
              <ShieldCheck size={13}/>
              <span>Read-only operational view · Matches orchestrated by carekiki MET Engine</span>
            </div>
            <div className="ck-mono">v0.1 · prototype</div>
          </footer>

          </>)}

        </div>

        {toast && (
          <div className="ck-toast">
            <Check size={16} style={{color: '#7FCBA9'}}/> {toast}
          </div>
        )}
      </div>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, detail, accent }) {
  return (
    <div className="ck-card p-5 relative overflow-hidden">
      <div className="absolute top-0 left-0 right-0 h-[3px]" style={{background: accent}}/>
      <div className="flex items-start justify-between mb-3">
        <div className="text-[11px] font-bold uppercase tracking-[0.16em]" style={{color: 'var(--ck-ink-3)'}}>{label}</div>
        <Icon size={16} style={{color: accent}}/>
      </div>
      <div className="ck-display text-[42px] font-medium leading-none mb-2" style={{color: 'var(--ck-ink)'}}>{value}</div>
      <div className="text-xs" style={{color: 'var(--ck-ink-2)'}}>{detail}</div>
    </div>
  );
}

function LegendDot({ color, label }) {
  return (
    <div className="flex items-center gap-2">
      <div className="w-3 h-3 rounded-sm" style={{background: color}}/>
      <span className="font-medium">{label}</span>
    </div>
  );
}

function ApiStatus({ apiState, onRefresh }) {
  const { status, error, lastSync } = apiState;

  let dot, label, detail;
  if (status === 'loading') {
    dot = <Loader2 size={11} style={{color: 'var(--ck-ink-3)'}} className="animate-spin"/>;
    label = 'Connecting…';
    detail = `${API_BASE || '(same-origin)'}${DASHBOARD_ENDPOINT}`;
  } else if (status === 'live') {
    dot = <span className="ck-pulse" style={{color: 'var(--ck-primary)'}}>●</span>;
    label = `Live · ${lastSync} SGT`;
    detail = 'Connected to MET Transport';
  } else if (status === 'error') {
    dot = <AlertCircle size={11} style={{color: 'var(--ck-amber)'}}/>;
    label = USE_MOCK_FALLBACK ? 'Offline · using fallback' : 'Offline';
    detail = error;
  } else {
    dot = <span style={{color: 'var(--ck-ink-3)'}}>○</span>;
    label = 'Idle';
    detail = '';
  }

  return (
    <div className="text-right">
      <div className="text-xs uppercase tracking-[0.18em] mb-1" style={{color: 'var(--ck-ink-3)'}}>Sync</div>
      <div className="ck-mono text-sm flex items-center gap-2 justify-end" style={{color: 'var(--ck-ink-2)'}}>
        {dot} {label}
        <button
          onClick={onRefresh}
          disabled={status === 'loading'}
          className="ml-1 p-1 rounded hover:bg-black/5 disabled:opacity-40 transition"
          title="Refresh"
        >
          <RefreshCw size={12} style={{color: 'var(--ck-ink-3)'}}/>
        </button>
      </div>
      {detail && (
        <div className="text-[10px] mt-1 ck-mono" style={{color: 'var(--ck-ink-3)'}}>
          {detail}
        </div>
      )}
    </div>
  );
}

function TabButton({ active, onClick, icon: Icon, label, total, onDuty }) {
  return (
    <button onClick={onClick} className={`ck-tab ${active ? 'active' : ''}`}>
      <Icon size={14}/>
      <span>{label}</span>
      <span className="count">{onDuty}/{total}</span>
    </button>
  );
}

function EmptyState({ area, type }) {
  return (
    <div className="px-6 py-10 text-center text-sm" style={{color: 'var(--ck-ink-3)'}}>
      No {type} based in <span style={{color: 'var(--ck-ink-2)', fontWeight: 600}}>{area}</span>.
    </div>
  );
}

function ResourceRow({ resource, type, trip, selectedTripId, onSelect, isLast }) {
  const isOnDuty = !!trip;
  const status = trip ? STATUS_STYLES[trip.status] : null;

  return (
    <div className="flex" style={{borderBottom: isLast ? 'none' : '1px solid var(--ck-line)'}}>
      {/* Name column */}
      <div className="px-5 py-4 flex-shrink-0" style={{width: 220, borderRight: '1px solid var(--ck-line)'}}>
        <div className="font-semibold text-[13.5px] leading-tight" style={{color: 'var(--ck-ink)'}}>
          {resource.name}
        </div>
        <div className="text-[11px] mt-1" style={{color: 'var(--ck-ink-3)'}}>
          {type === 'driver' ? resource.vehicle : resource.languages.join(' · ')}
        </div>
        <div className="flex items-center gap-1.5 mt-2 flex-wrap">
          <span className="ck-tag" style={{background: '#E6EFE8', color: 'var(--ck-primary)', borderColor: '#C4DACA'}}>
            <MapPin size={10}/> {resource.area}
          </span>
          {type === 'driver' && resource.wheelchair && (
            <span className="ck-tag"><Accessibility size={10}/> WCA</span>
          )}
          {type === 'escort' && resource.dementia && (
            <span className="ck-tag"><Brain size={10}/> Dementia-trained</span>
          )}
          {!isOnDuty && (
            <span className="ck-tag" style={{background: '#EFE9D5', color: 'var(--ck-ink-3)'}}>
              <Coffee size={10}/> Off-duty
            </span>
          )}
        </div>
      </div>

      {/* Timeline column */}
      <div className="relative" style={{width: TIMELINE_WIDTH, height: 86}}>
        {/* hour gridlines */}
        {Array.from({length: HOURS + 1}).map((_, i) => (
          <div key={i} className="absolute top-0 bottom-0 w-px"
               style={{left: i * PX_PER_HOUR, background: i % 2 === 0 ? 'var(--ck-line)' : 'rgba(217,210,189,0.5)'}}/>
        ))}

        {/* now indicator (10:42) */}
        <div className="ck-now-line" style={{left: timeToPx('10:42')}}/>

        {!isOnDuty && (
          <div className="ck-empty-slot" style={{left: 14, right: 14}}>
            Available · no assignments
          </div>
        )}

        {trip && (
          <TripBlock
            trip={trip}
            status={status}
            selected={selectedTripId === trip.id}
            onSelect={() => onSelect(trip.id)}
          />
        )}
      </div>
    </div>
  );
}

function TripBlock({ trip, status, selected, onSelect }) {
  const left = timeToPx(trip.pickup.time);
  const right = timeToPx(trip.returnTime);
  const width = right - left;
  const Icon = status.Icon;

  return (
    <div
      onClick={onSelect}
      className={`ck-trip-block ${selected ? 'selected' : ''}`}
      style={{
        left, width,
        background: status.bg,
        color: status.text,
        border: `1px solid ${status.border}`,
      }}
    >
      <div className="accent-bar" style={{background: status.accent}}/>
      <div className="flex items-start justify-between gap-2">
        <div className="name truncate">{trip.elderly}</div>
        <Icon size={13} style={{flexShrink: 0, marginTop: 1, opacity: 0.9}} className={trip.status === 'in-progress' ? 'ck-pulse' : ''}/>
      </div>
      <div className="meta ck-mono">
        {trip.pickup.time} → {trip.returnTime} · {trip.appointment.location.split(' ').slice(-2).join(' ')}
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════
// DRIVER / ESCORT VIEW
// ═══════════════════════════════════════════════════════════════════════

function DriverEscortView({ drivers, escorts, trips, showToast }) {
  // Build a unified roster: drivers + escorts with role tag
  const roster = useMemo(() => [
    ...drivers.map(d => ({ ...d, role: 'driver' })),
    ...escorts.map(e => ({ ...e, role: 'escort' })),
  ], [drivers, escorts]);

  const [selectedId, setSelectedId] = useState(roster[0]?.id || null);
  const [activeTab, setActiveTab] = useState('pending');
  const [pending, setPending] = useState([]);
  const [current, setCurrent] = useState(null);
  const [loading, setLoading] = useState(false);
  const [rejectingTrip, setRejectingTrip] = useState(null);
  const [arrivalNotified, setArrivalNotified] = useState({}); // { tripId: true }
  const [actionLoading, setActionLoading] = useState({});     // { tripId: 'accept' | 'reject' | 'arrival' }

  const me = roster.find(r => r.id === selectedId);

  // Fetch pending + current bookings whenever identity changes
  useEffect(() => {
    if (!me) return;
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}${MY_BOOKINGS_ENDPOINT}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ resource_id: me.id, role: me.role }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (cancelled) return;
        setPending(data.pending || []);
        setCurrent(data.current || null);
      } catch (err) {
        if (cancelled) return;
        if (USE_MOCK_FALLBACK) {
          // Build pending + current from local mock data
          const idField = me.role === 'driver' ? 'driverId' : 'escortId';
          const myPending = MOCK_PENDING.filter(p => p[idField] === me.id);
          const myCurrent = trips.find(t =>
            t[idField] === me.id && (t.status === 'in-progress' || t.status === 'upcoming')
          );
          setPending(myPending);
          setCurrent(myCurrent || null);
        } else {
          setPending([]); setCurrent(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [selectedId]);

  const handleAccept = async (trip) => {
    setActionLoading(s => ({ ...s, [trip.id]: 'accept' }));
    try {
      await fetch(`${API_BASE}${ACCEPT_ENDPOINT}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trip_id: trip.id, resource_id: me.id }),
      }).catch(() => null); // swallow for mock fallback
      // optimistic: remove from pending, set as current
      setPending(p => p.filter(x => x.id !== trip.id));
      setCurrent({ ...trip, status: 'upcoming' });
      showToast(`Accepted booking for ${trip.elderly}`);
      setActiveTab('current');
    } finally {
      setActionLoading(s => { const n = { ...s }; delete n[trip.id]; return n; });
    }
  };

  const handleReject = async (trip, reason) => {
    setActionLoading(s => ({ ...s, [trip.id]: 'reject' }));
    setRejectingTrip(null);
    try {
      let nextMatch = null;
      try {
        const res = await fetch(`${API_BASE}${REJECT_ENDPOINT}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ trip_id: trip.id, resource_id: me.id, reason }),
        });
        if (res.ok) {
          const data = await res.json();
          nextMatch = data.next_match || null;
        }
      } catch {}
      // mock fallback: produce a replacement match
      if (!nextMatch && USE_MOCK_FALLBACK) {
        const idField = me.role === 'driver' ? 'driverId' : 'escortId';
        nextMatch = { ...MOCK_REPLACEMENT_MATCH, id: `p-rep-${Date.now()}`, [idField]: me.id };
      }
      setPending(p => {
        const filtered = p.filter(x => x.id !== trip.id);
        return nextMatch ? [...filtered, nextMatch] : filtered;
      });
      showToast(nextMatch ? `Declined · next-best match incoming` : `Declined`);
    } finally {
      setActionLoading(s => { const n = { ...s }; delete n[trip.id]; return n; });
    }
  };

  const handleNotifyArrival = async () => {
    if (!current) return;
    setActionLoading(s => ({ ...s, [current.id]: 'arrival' }));
    try {
      await fetch(`${API_BASE}${NOTIFY_ARRIVAL_ENDPOINT}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trip_id: current.id, resource_id: me.id }),
      }).catch(() => null);
      setArrivalNotified(s => ({ ...s, [current.id]: true }));
      showToast(`Caregiver notified · 10 mins ETA`);
    } finally {
      setActionLoading(s => { const n = { ...s }; delete n[current.id]; return n; });
    }
  };

  if (!me) {
    return <div className="ck-card p-6 text-sm" style={{color: 'var(--ck-ink-3)'}}>No drivers or escorts available.</div>;
  }

  const initial = me.name.charAt(0);

  return (
    <>
      {/* ─── IDENTITY HEADER ─── */}
      <div className="ck-identity-card mb-6">
        <div className="flex items-center gap-4">
          <div className="ck-identity-avatar">{initial}</div>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.18em] mb-1" style={{color: 'var(--ck-ink-3)'}}>
              Signed in as · {me.role}
            </div>
            <div className="ck-display text-[26px] font-medium leading-tight">{me.name}</div>
            <div className="flex items-center gap-2 mt-1 text-xs" style={{color: 'var(--ck-ink-3)'}}>
              <MapPin size={11}/> {me.area}
              <span>·</span>
              <span className="ck-mono">{me.phone}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-[0.18em]" style={{color: 'var(--ck-ink-3)'}}>
            Switch identity
          </span>
          <select
            className="ck-identity-select"
            value={selectedId}
            onChange={e => { setSelectedId(e.target.value); setActiveTab('pending'); }}
          >
            <optgroup label="Drivers">
              {drivers.map(d => <option key={d.id} value={d.id}>{d.name} · {d.area}</option>)}
            </optgroup>
            <optgroup label="Escorts">
              {escorts.map(e => <option key={e.id} value={e.id}>{e.name} · {e.area}</option>)}
            </optgroup>
          </select>
        </div>
      </div>

      {/* ─── SUB TABS ─── */}
      <div className="ck-tab-bar" style={{borderRadius: 12, border: '1px solid var(--ck-line)', marginBottom: 16, background: 'var(--ck-surface)'}}>
        <button
          className={`ck-tab ${activeTab === 'pending' ? 'active' : ''}`}
          onClick={() => setActiveTab('pending')}
        >
          <Inbox size={14}/> Pending Requests
          <span className="count">{pending.length}</span>
        </button>
        <button
          className={`ck-tab ${activeTab === 'current' ? 'active' : ''}`}
          onClick={() => setActiveTab('current')}
        >
          <CircleDot size={14}/> Current Booking
          <span className="count">{current ? 1 : 0}</span>
        </button>
      </div>

      {/* ─── CONTENT ─── */}
      {loading && (
        <div className="ck-card p-10 flex items-center justify-center gap-3 text-sm" style={{color: 'var(--ck-ink-3)'}}>
          <Loader2 size={16} className="animate-spin"/> Loading bookings…
        </div>
      )}

      {!loading && activeTab === 'pending' && (
        pending.length === 0 ? (
          <div className="ck-card p-12 text-center">
            <Inbox size={28} style={{color: 'var(--ck-ink-3)', margin: '0 auto 12px'}}/>
            <div className="ck-display text-[20px] font-medium mb-1">No pending requests</div>
            <div className="text-sm" style={{color: 'var(--ck-ink-3)'}}>
              MET Transport hasn't matched you with a new booking yet.
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {pending.map(trip => (
              <PendingRequestCard
                key={trip.id}
                trip={trip}
                role={me.role}
                onAccept={() => handleAccept(trip)}
                onReject={() => setRejectingTrip(trip)}
                actionLoading={actionLoading[trip.id]}
              />
            ))}
          </div>
        )
      )}

      {!loading && activeTab === 'current' && (
        current ? (
          <CurrentBookingCard
            trip={current}
            role={me.role}
            onNotifyArrival={handleNotifyArrival}
            arrivalNotified={!!arrivalNotified[current.id]}
            arrivalLoading={actionLoading[current.id] === 'arrival'}
          />
        ) : (
          <div className="ck-card p-12 text-center">
            <CircleDashed size={28} style={{color: 'var(--ck-ink-3)', margin: '0 auto 12px'}}/>
            <div className="ck-display text-[20px] font-medium mb-1">No active booking</div>
            <div className="text-sm" style={{color: 'var(--ck-ink-3)'}}>
              Accept a request from the Pending tab to see it here.
            </div>
          </div>
        )
      )}

      {/* ─── REJECT MODAL ─── */}
      {rejectingTrip && (
        <RejectModal
          trip={rejectingTrip}
          onCancel={() => setRejectingTrip(null)}
          onSubmit={(reason) => handleReject(rejectingTrip, reason)}
        />
      )}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Pending request card
// ─────────────────────────────────────────────────────────────────────

function PendingRequestCard({ trip, role, onAccept, onReject, actionLoading }) {
  return (
    <div className="ck-request-card">
      <div className="header">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.2em] mb-1" style={{color: '#7B5BA6'}}>
            <Inbox size={10} style={{display: 'inline', marginRight: 4, marginBottom: 2}}/> New Request · {trip.id.toUpperCase()}
          </div>
          <div className="ck-display text-[20px] font-medium leading-tight">{trip.elderly}</div>
          <div className="text-xs mt-1" style={{color: 'var(--ck-ink-3)'}}>
            Age {trip.age} · {trip.accessibility === 'wheelchair' ? 'Wheelchair user' : 'Ambulant'}
          </div>
        </div>
        {trip.matchScore && (
          <div className="ck-match-score">
            <ShieldCheck size={11}/> {trip.matchScore}% match
          </div>
        )}
      </div>

      <div className="p-5 space-y-4">
        {/* Pickup → Appointment */}
        <div className="grid grid-cols-2 gap-4">
          <RequestDetailBlock label="Pickup" icon={MapPin}>
            <div className="ck-mono font-bold text-[14px]">{trip.pickup.time}</div>
            {trip.pickup.date && <div className="text-xs ck-mono" style={{color: 'var(--ck-ink-3)'}}>{trip.pickup.date}</div>}
            <div className="mt-1 text-[13px]" style={{color: 'var(--ck-ink-2)'}}>{trip.pickup.location}</div>
          </RequestDetailBlock>
          <RequestDetailBlock label="Appointment" icon={Clock}>
            <div className="ck-mono font-bold text-[14px]">{trip.appointment.time}</div>
            <div className="mt-1 text-[13px]" style={{color: 'var(--ck-ink-2)'}}>{trip.appointment.location}</div>
            <div className="text-xs mt-0.5" style={{color: 'var(--ck-ink-3)'}}>{trip.appointment.clinic}</div>
          </RequestDetailBlock>
        </div>

        {/* Match reasons */}
        {trip.matchReasons && trip.matchReasons.length > 0 && (
          <div className="pt-3" style={{borderTop: '1px solid var(--ck-line)'}}>
            <div className="text-[10px] font-bold uppercase tracking-[0.16em] mb-2" style={{color: 'var(--ck-ink-3)'}}>
              Why you were matched
            </div>
            <div className="flex flex-wrap gap-1.5">
              {trip.matchReasons.map((r, i) => (
                <span key={i} className="ck-tag" style={{background: '#E6EFE8', color: 'var(--ck-primary-2)', borderColor: '#C4DACA'}}>
                  <Check size={10}/> {r}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Caregiver + subsidy */}
        <div className="grid grid-cols-2 gap-4 pt-3" style={{borderTop: '1px solid var(--ck-line)'}}>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.16em] mb-1" style={{color: 'var(--ck-ink-3)'}}>Caregiver</div>
            <div className="text-[13px] font-semibold">{trip.caregiver}</div>
            <div className="ck-mono text-xs mt-0.5" style={{color: 'var(--ck-ink-2)'}}>{trip.caregiverPhone}</div>
          </div>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.16em] mb-1" style={{color: 'var(--ck-ink-3)'}}>Subsidy</div>
            <span className="ck-tag" style={{background: 'var(--ck-primary)', color: 'var(--ck-surface)', borderColor: 'var(--ck-primary-2)'}}>
              <ShieldCheck size={10}/> {trip.subsidy}
            </span>
          </div>
        </div>

        {trip.notes && (
          <div className="pt-3 text-xs italic" style={{borderTop: '1px solid var(--ck-line)', color: 'var(--ck-ink-2)'}}>
            <strong style={{color: 'var(--ck-ink-3)', fontStyle: 'normal'}}>NOTE · </strong>{trip.notes}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <button
            className="ck-action-btn ck-action-reject"
            onClick={onReject}
            disabled={!!actionLoading}
          >
            {actionLoading === 'reject' ? <Loader2 size={16} className="animate-spin"/> : <X size={16}/>}
            Decline
          </button>
          <button
            className="ck-action-btn ck-action-accept"
            onClick={onAccept}
            disabled={!!actionLoading}
          >
            {actionLoading === 'accept' ? <Loader2 size={16} className="animate-spin"/> : <Check size={16}/>}
            Accept booking
          </button>
        </div>
      </div>
    </div>
  );
}

function RequestDetailBlock({ label, icon: Icon, children }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2 text-[10px] font-bold uppercase tracking-[0.16em]" style={{color: 'var(--ck-ink-3)'}}>
        <Icon size={11}/> {label}
      </div>
      {children}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Current booking card
// ─────────────────────────────────────────────────────────────────────

function CurrentBookingCard({ trip, role, onNotifyArrival, arrivalNotified, arrivalLoading }) {
  const status = STATUS_STYLES[trip.status] || STATUS_STYLES.upcoming;
  const StatusIcon = status.Icon;

  return (
    <div className="ck-card overflow-hidden">
      <div className="px-6 py-5 flex items-center justify-between" style={{background: status.bg, color: status.text}}>
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.2em] opacity-85 mb-1">Active Booking · {trip.id.toUpperCase()}</div>
          <div className="ck-display text-[26px] leading-tight font-medium">{trip.elderly}</div>
          <div className="text-xs mt-1 opacity-90">
            Age {trip.age} · {trip.accessibility === 'wheelchair' ? 'Wheelchair user' : 'Ambulant'}
          </div>
        </div>
        <span className="ck-status-pill" style={{background: 'rgba(255,255,255,0.18)', color: status.text}}>
          <StatusIcon size={12} className={trip.status === 'in-progress' ? 'ck-pulse' : ''}/> {status.label}
        </span>
      </div>

      <div className="p-6 space-y-5">
        {/* Pickup */}
        <div className="flex gap-4">
          <div className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0" style={{background: 'var(--ck-bg-2)', color: 'var(--ck-primary)'}}>
            <MapPin size={16}/>
          </div>
          <div className="flex-1">
            <div className="text-[10px] font-bold uppercase tracking-[0.16em] mb-1" style={{color: 'var(--ck-ink-3)'}}>Pickup</div>
            <div className="ck-mono font-bold text-[15px]">{trip.pickup.time}</div>
            <div className="text-sm mt-0.5" style={{color: 'var(--ck-ink-2)'}}>{trip.pickup.location}</div>
          </div>
        </div>

        <div className="flex justify-center" style={{color: 'var(--ck-ink-3)'}}>
          <ArrowRight size={18}/>
        </div>

        {/* Appointment */}
        <div className="flex gap-4">
          <div className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0" style={{background: 'var(--ck-bg-2)', color: 'var(--ck-primary)'}}>
            <Clock size={16}/>
          </div>
          <div className="flex-1">
            <div className="text-[10px] font-bold uppercase tracking-[0.16em] mb-1" style={{color: 'var(--ck-ink-3)'}}>Appointment</div>
            <div className="ck-mono font-bold text-[15px]">{trip.appointment.time}</div>
            <div className="text-sm mt-0.5" style={{color: 'var(--ck-ink-2)'}}>{trip.appointment.location}</div>
            <div className="text-xs mt-0.5" style={{color: 'var(--ck-ink-3)'}}>{trip.appointment.clinic}</div>
          </div>
        </div>

        {/* Caregiver */}
        <div className="pt-4 grid grid-cols-2 gap-4" style={{borderTop: '1px solid var(--ck-line)'}}>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.16em] mb-1" style={{color: 'var(--ck-ink-3)'}}>Caregiver</div>
            <div className="text-[14px] font-semibold">{trip.caregiver}</div>
            <a href={`tel:${trip.caregiverPhone}`} className="ck-mono text-xs mt-1 inline-flex items-center gap-1.5" style={{color: 'var(--ck-primary)'}}>
              <Phone size={11}/> {trip.caregiverPhone}
            </a>
          </div>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.16em] mb-1" style={{color: 'var(--ck-ink-3)'}}>Return time</div>
            <div className="ck-mono font-bold text-[14px]">{trip.returnTime}</div>
          </div>
        </div>

        {trip.notes && (
          <div className="pt-3 text-xs italic" style={{borderTop: '1px solid var(--ck-line)', color: 'var(--ck-ink-2)'}}>
            <strong style={{color: 'var(--ck-ink-3)', fontStyle: 'normal'}}>NOTE · </strong>{trip.notes}
          </div>
        )}

        {/* Notify arrival button */}
        <div className="pt-3">
          <button
            className="ck-notify-btn"
            onClick={onNotifyArrival}
            disabled={arrivalNotified || arrivalLoading}
          >
            {arrivalLoading ? (
              <><Loader2 size={18} className="animate-spin"/> Notifying caregiver…</>
            ) : arrivalNotified ? (
              <><Check size={18}/> Caregiver notified · awaiting pickup</>
            ) : (
              <><Bell size={18}/> I am 10 mins away</>
            )}
          </button>
          {!arrivalNotified && !arrivalLoading && (
            <div className="text-[11px] text-center mt-2" style={{color: 'var(--ck-ink-3)'}}>
              Sends a WhatsApp notification to {trip.caregiver}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Reject modal
// ─────────────────────────────────────────────────────────────────────

const REJECT_REASONS = [
  { id: 'schedule', label: 'Schedule conflict' },
  { id: 'vehicle',  label: 'Vehicle unavailable' },
  { id: 'distance', label: 'Outside my service area' },
  { id: 'medical',  label: 'Cannot meet patient needs' },
  { id: 'other',    label: 'Other (please specify)' },
];

function RejectModal({ trip, onCancel, onSubmit }) {
  const [selectedReason, setSelectedReason] = useState(null);
  const [details, setDetails] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const canSubmit = selectedReason && (selectedReason !== 'other' || details.trim().length > 0);

  const submit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    const reasonLabel = REJECT_REASONS.find(r => r.id === selectedReason).label;
    const fullReason = details.trim() ? `${reasonLabel} — ${details.trim()}` : reasonLabel;
    await onSubmit(fullReason);
    setSubmitting(false);
  };

  return (
    <div className="ck-modal-backdrop" onClick={onCancel}>
      <div className="ck-modal" onClick={e => e.stopPropagation()}>
        <div className="px-6 py-5" style={{borderBottom: '1px solid var(--ck-line)'}}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.18em] mb-1" style={{color: 'var(--ck-rose)'}}>
                Decline request
              </div>
              <div className="ck-display text-[22px] font-medium leading-tight">Why are you declining?</div>
              <div className="text-xs mt-1.5" style={{color: 'var(--ck-ink-3)'}}>
                Booking · {trip.id.toUpperCase()} for {trip.elderly}
              </div>
            </div>
            <button onClick={onCancel} className="p-1 rounded hover:bg-black/5">
              <X size={18} style={{color: 'var(--ck-ink-3)'}}/>
            </button>
          </div>
        </div>

        <div className="p-6 space-y-3">
          <div className="text-[11px] font-bold uppercase tracking-[0.16em] mb-1" style={{color: 'var(--ck-ink-3)'}}>
            Select a reason
          </div>
          {REJECT_REASONS.map(r => (
            <div
              key={r.id}
              className={`ck-radio-row ${selectedReason === r.id ? 'selected' : ''}`}
              onClick={() => setSelectedReason(r.id)}
            >
              <div className="ck-radio-dot"/>
              <div className="text-[13px] font-medium">{r.label}</div>
            </div>
          ))}

          {selectedReason && (
            <div className="pt-2">
              <div className="text-[11px] font-bold uppercase tracking-[0.16em] mb-2" style={{color: 'var(--ck-ink-3)'}}>
                {selectedReason === 'other' ? 'Please specify' : 'Additional details (optional)'}
              </div>
              <textarea
                className="ck-textarea"
                placeholder="Add any context that would help dispatch find a better match…"
                value={details}
                onChange={e => setDetails(e.target.value)}
              />
            </div>
          )}
        </div>

        <div className="px-6 pb-6 flex gap-3">
          <button
            onClick={onCancel}
            className="ck-action-btn ck-action-reject"
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            onClick={submit}
            className="ck-action-btn"
            disabled={!canSubmit || submitting}
            style={{
              background: canSubmit ? 'var(--ck-rose)' : 'var(--ck-bg-2)',
              color: canSubmit ? 'var(--ck-surface)' : 'var(--ck-ink-3)',
              borderColor: canSubmit ? '#8C2F38' : 'var(--ck-line)',
            }}
          >
            {submitting ? (
              <><Loader2 size={16} className="animate-spin"/> Finding next match…</>
            ) : (
              <><X size={16}/> Submit & re-match</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
