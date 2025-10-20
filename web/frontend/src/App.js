import React, { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Modal,
  Box,
  CircularProgress,
  Alert,
  CssBaseline,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
  Grid
} from '@mui/material';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import NewsSignals from './components/NewsSignals';

// Professional and modern theme
const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    background: {
      default: '#f4f6f8',
      paper: '#ffffff',
    },
  },
  typography: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    h4: {
      fontWeight: 600,
    },
    h5: {
      fontWeight: 600,
    },
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          boxShadow: '0px 4px 20px rgba(0, 0, 0, 0.05)',
        },
      },
    },
  },
});

const modalStyle = {
  position: 'absolute',
  top: '50%',
  left: '50%',
  transform: 'translate(-50%, -50%)',
  width: '70%',
  maxWidth: '900px',
  bgcolor: 'background.paper',
  borderRadius: 2,
  boxShadow: 24,
  p: 4,
  maxHeight: '90vh',
  overflowY: 'auto',
};

const statusMap = {
    'new': 'New',
    'downloading': 'In Progress',
    'parsing': 'In Progress',
    'classifying': 'In Progress',
    'summarizing': 'In Progress',
    'extracting': 'In Progress',
    'self_checking': 'In Progress',
    'classified': 'Processed',
    'summarized': 'Processed',
    'info_extracted': 'Processed',
    'completed': 'Completed',
    'processing_failed': 'Failed',
    'summarization_failed': 'Failed',
    'extraction_failed': 'Failed',
    'self_check_failed': 'Failed',
};

const getStatusChip = (status) => {
  let color = 'default';
  const label = statusMap[status] || status.charAt(0).toUpperCase() + status.slice(1);

  switch (label) {
    case 'New': color = 'primary'; break;
    case 'In Progress': color = 'warning'; break;
    case 'Processed': color = 'info'; break;
    case 'Completed': color = 'success'; break;
    case 'Failed': color = 'error'; break;
    default: break;
  }
  return <Chip label={label} color={color} size="small" />;
};


function App() {
  const [filings, setFilings] = useState([]);
  const [filteredFilings, setFilteredFilings] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedFiling, setSelectedFiling] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState({ msg: '', type: '' });
  const [filters, setFilters] = useState({ search: '', status: '' });

  const uniqueStatuses = ['All', ...new Set(Object.values(statusMap))];

  const fetchFilings = async () => {
    try {
      // setLoading(true); // Don't show main loader on background refresh
      const response = await fetch('http://localhost:8000/api/v1/filings');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setFilings(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (event) => {
    setSelectedFile(event.target.files[0]);
    setUploadStatus({ msg: '', type: '' });
  };

  const handleFilterChange = (event) => {
    const { name, value } = event.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setUploadStatus({ msg: 'Please select a file first.', type: 'error' });
      return;
    }

    const formData = new FormData();
    formData.append('file', selectedFile);

    setUploading(true);
    setUploadStatus({ msg: 'Uploading...', type: 'info' });

    try {
      const response = await fetch('http://localhost:8000/api/v1/filings/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      setUploadStatus({ msg: `File uploaded successfully! Filing ID: ${result.id}`, type: 'success' });
      setSelectedFile(null);
      if(document.getElementById('file-input')) {
        document.getElementById('file-input').value = ''; // Reset file input
      }
      fetchFilings(); // Refresh the list
    } catch (e) {
      setUploadStatus({ msg: e.message, type: 'error' });
    } finally {
      setUploading(false);
    }
  };


  const handleOpen = async (filingId) => {
    setDetailsLoading(true);
    setOpen(true);
    try {
      const response = await fetch(`http://localhost:8000/api/v1/filings/${filingId}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setSelectedFiling(data);
    } catch (e) {
      setError(e.message);
      setSelectedFiling(null);
    } finally {
      setDetailsLoading(false);
    }
  };
  
  const handleClose = () => {
    setOpen(false);
    setSelectedFiling(null);
  };

  useEffect(() => {
    fetchFilings();
    const interval = setInterval(fetchFilings, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    let result = filings;
    if (filters.status && filters.status !== 'All') {
      result = result.filter(f => statusMap[f.analysis_status] === filters.status);
    }
    if (filters.search) {
      const searchTerm = filters.search.toLowerCase();
      result = result.filter(f => 
        f.corp_name.toLowerCase().includes(searchTerm) || 
        f.ticker.toLowerCase().includes(searchTerm)
      );
    }
    setFilteredFilings(result);
  }, [filings, filters]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
        <Typography variant="h4" gutterBottom component="h1">
          K-Finance AI Research Copilot
        </Typography>

        <NewsSignals />


        <Paper sx={{ p: 2, mb: 4 }}>
          <Typography variant="h6" gutterBottom>Upload Filing PDF</Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Button
              variant="contained"
              component="label"
            >
              Choose File
              <input
                id="file-input"
                type="file"
                hidden
                onChange={handleFileChange}
                accept="application/pdf"
              />
            </Button>
            {selectedFile && <Typography variant="body1">{selectedFile.name}</Typography>}
            <Button
              variant="contained"
              color="primary"
              onClick={handleUpload}
              disabled={uploading || !selectedFile}
              sx={{ minWidth: '100px' }}
            >
              {uploading ? <CircularProgress size={24} color="inherit" /> : 'Upload'}
            </Button>
          </Box>
          {uploadStatus.msg && (
            <Alert severity={uploadStatus.type} sx={{ mt: 2 }}>
              {uploadStatus.msg}
            </Alert>
          )}
        </Paper>
        
        <Typography variant="h5" gutterBottom>Analysis Pipeline</Typography>
        <Paper sx={{ p: 2, mb: 2 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={8}>
              <TextField
                fullWidth
                variant="outlined"
                label="Search by Corporation or Ticker"
                name="search"
                value={filters.search}
                onChange={handleFilterChange}
                size="small"
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <FormControl fullWidth size="small">
                <InputLabel>Status</InputLabel>
                <Select
                  name="status"
                  value={filters.status}
                  label="Status"
                  onChange={handleFilterChange}
                >
                  {uniqueStatuses.map(s => <MenuItem key={s} value={s}>{s}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </Paper>

        {loading && !filings.length ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
            <CircularProgress />
          </Box>
        ) : error ? (
          <Alert severity="error">Error fetching data: {error}</Alert>
        ) : (
          <TableContainer component={Paper}>
            <Table sx={{ minWidth: 650 }} aria-label="filings table">
              <TableHead>
                <TableRow>
                  <TableCell>Corporation</TableCell>
                  <TableCell>Report Title</TableCell>
                  <TableCell>Filed At</TableCell>
                  <TableCell>Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredFilings.map((filing) => (
                  <TableRow
                    key={filing.id}
                    hover
                    onClick={() => handleOpen(filing.id)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell component="th" scope="row">
                      {filing.corp_name} ({filing.ticker})
                    </TableCell>
                    <TableCell>{filing.title}</TableCell>
                    <TableCell>{new Date(filing.filed_at).toLocaleDateString()}</TableCell>
                    <TableCell>{getStatusChip(filing.analysis_status)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
             {filteredFilings.length === 0 && !loading && (
              <Typography sx={{ p: 2, textAlign: 'center' }}>No filings match the current filters.</Typography>
            )}
          </TableContainer>
        )}

        <Modal
          open={open}
          onClose={handleClose}
          aria-labelledby="filing-details-modal-title"
        >
          <Box sx={modalStyle}>
            {detailsLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
                <CircularProgress />
              </Box>
            ) : selectedFiling ? (
              <>
                <Typography id="filing-details-modal-title" variant="h5" component="h2">
                  {selectedFiling.title}
                </Typography>
                <Typography variant="subtitle1" color="text.secondary" gutterBottom>
                  {selectedFiling.corp_name} | Filed on: {new Date(selectedFiling.filed_at).toLocaleDateString()}
                </Typography>

                {selectedFiling.summary && (
                  <Box mt={3}>
                    <Typography variant="h6">5W1H Summary</Typography>
                    <Paper variant="outlined" sx={{ p: 2, mt: 1, backgroundColor: '#f9f9f9' }}>
                      {Object.entries(selectedFiling.summary.fiveW1H).map(([key, value]) => (
                        <Typography key={key} variant="body2" sx={{ mb: 1 }}>
                          <strong>{key.toUpperCase()}:</strong> {value}
                        </Typography>
                      ))}
                    </Paper>
                  </Box>
                )}

                {selectedFiling.facts && selectedFiling.facts.length > 0 && (
                  <Box mt={3}>
                    <Typography variant="h6">Key Extracted Facts</Typography>
                    <TableContainer component={Paper} variant="outlined" sx={{ mt: 1 }}>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Key</TableCell>
                            <TableCell>Value</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {selectedFiling.facts.map((fact) => (
                            <TableRow key={fact.id}>
                              <TableCell>{fact.key}</TableCell>
                              <TableCell>{fact.value} {fact.unit || ''}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </Box>
                )}
              </>
            ) : (
              <Alert severity="info">No details available for this filing.</Alert>
            )}
          </Box>
        </Modal>
      </Container>
    </ThemeProvider>
  );
}

export default App;