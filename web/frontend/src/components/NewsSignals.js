
import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Alert,
  Link
} from '@mui/material';

const getSentimentColor = (sentiment) => {
  if (sentiment > 0.3) return 'success.main'; // 긍정 (녹색)
  if (sentiment < -0.3) return 'error.main'; // 부정 (적색)
  return 'text.secondary'; // 중립 (회색)
};

function NewsSignals() {
  const [news, setNews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchNews = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/v1/news');
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        setNews(data);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };

    fetchNews();
    const interval = setInterval(fetchNews, 15000); // 15초마다 뉴스 새로고침
    return () => clearInterval(interval);
  }, []);

  if (loading && !news.length) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error" sx={{ my: 2 }}>Error fetching news: {error}</Alert>;
  }

  return (
    <Box sx={{ mb: 4 }}>
      <Typography variant="h5" gutterBottom>Market Mood</Typography>
      {news.length === 0 && !loading ? (
        <Typography sx={{ p: 2, textAlign: 'center' }}>No news signals found.</Typography>
      ) : (
        <Grid container spacing={2}>
          {news.map((item) => (
            <Grid item xs={12} sm={6} md={4} key={item.id}>
              <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <CardContent sx={{ flexGrow: 1 }}>
                  <Typography variant="subtitle2" component="div" gutterBottom>
                    <Link href={item.url} target="_blank" rel="noopener noreferrer" underline="hover">
                      {item.headline}
                    </Link>
                  </Typography>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Typography variant="caption" color="text.secondary">
                      {item.source} | {new Date(item.published_at).toLocaleDateString()}
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <Box sx={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: getSentimentColor(item.sentiment) }} />
                      <Typography variant="caption" sx={{ color: getSentimentColor(item.sentiment), fontWeight: 'bold' }}>
                        {item.sentiment?.toFixed(2)}
                      </Typography>
                    </Box>
                  </Box>
                  <Box>
                    {item.topics?.map((topic) => (
                      <Chip key={topic} label={topic} size="small" sx={{ mr: 0.5, mb: 0.5 }} />
                    ))}
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  );
}

export default NewsSignals;
