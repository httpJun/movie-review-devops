import http from 'k6/http';
import { check } from 'k6';

export const options = {
  noConnectionReuse: __ENV.NO_REUSE === 'true',
  scenarios: {
    movies: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.RATE || 10),
      timeUnit: '1s',
      duration: __ENV.DURATION || '60s',
      preAllocatedVUs: 100,
      maxVUs: 100,
      gracefulStop: '15s',
    },
  },
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

export default function () {
  const response = http.get('http://hpa-backend:8000/movies', {
    timeout: '10s',
  });

  check(response, {
    'HTTP 200': (r) => r.status === 200,
    '영화 100건': (r) => {
      try {
        const body = r.json();
        return Array.isArray(body) && body.length === 100;
      } catch (_) {
        return false;
      }
    },
  });
}
