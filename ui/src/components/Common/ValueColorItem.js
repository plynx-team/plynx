import React, { useState } from 'react';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import PropTypes from 'prop-types';

const PRESET_COLORS = [
  '#D0021B',
  '#F5A623',
  '#F8E71C',
  '#8B572A',
  '#7ED321',
  '#417505',
  '#BD10E0',
  '#9013FE',
  '#4A90E2',
  '#50E3C2',
  '#B8E986',
  '#000000',
  '#4A4A4A',
  '#9B9B9B',
  '#FFFFFF',
];

function SimpleDialog({ onClose, open, initColor }) {
  const [colorValue, setColorValue] = useState(initColor || '#000000');

  return (
    <Dialog onClose={() => onClose(colorValue)} open={open}>
      <DialogTitle>Select Color</DialogTitle>
      <DialogContent sx={{ minWidth: 240 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <input
            type="color"
            value={colorValue}
            onChange={(e) => setColorValue(e.target.value)}
            style={{ width: 48, height: 36, border: 'none', padding: 0, cursor: 'pointer', background: 'transparent' }}
          />
          <span style={{ fontFamily: 'monospace', fontSize: 14 }}>{colorValue}</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 32px)', gap: 8 }}>
          {PRESET_COLORS.map((preset) => (
            <button
              key={preset}
              type="button"
              aria-label={preset}
              onClick={() => setColorValue(preset)}
              style={{
                backgroundColor: preset,
                width: 32,
                height: 28,
                border: colorValue.toUpperCase() === preset.toUpperCase() ? '2px solid #12ccc8' : '1px solid #666',
                borderRadius: 4,
                cursor: 'pointer',
              }}
            />
          ))}
        </div>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => onClose(null)} color="inherit">
          Cancel
        </Button>
        <Button onClick={() => onClose(colorValue)} color="primary">
          Apply
        </Button>
      </DialogActions>
    </Dialog>
  );
}

SimpleDialog.propTypes = {
  onClose: PropTypes.func.isRequired,
  open: PropTypes.bool.isRequired,
  initColor: PropTypes.string.isRequired,
};

export default function ValueColorItem({ name, value, onChange }) {
  const [open, setOpen] = useState(false);
  const [colorValue, setColorValue] = useState(value);

  const handleClickOpen = () => {
    setOpen(true);
  };

  const handleClose = (valueOnClose) => {
    setOpen(false);
    if (valueOnClose) {
      setColorValue(valueOnClose);
      onChange({
        target: {
          name: name,
          value: valueOnClose,
          type: 'color',
        },
      });
    }
  };

  return (
    <div key={name} className="input-button">
      <Button variant="outlined" onClick={handleClickOpen}>
        <div
          style={{
            backgroundColor: colorValue,
            width: '20px',
            height: '20px',
            border: '1px solid #BBB',
            borderRadius: '2pt',
            marginRight: '3pt',
          }}
        />
        {colorValue}
      </Button>
      <SimpleDialog initColor={colorValue} open={open} onClose={handleClose} />
    </div>
  );
}

ValueColorItem.propTypes = {
  name: PropTypes.string.isRequired,
  value: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
};
