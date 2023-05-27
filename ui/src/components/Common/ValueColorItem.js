import React, { useState } from 'react';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import { SketchPicker } from 'react-color';
import PropTypes from 'prop-types';

function SimpleDialog(props) {
  const { onClose, open, initColor } = props;
  const [colorValue, setColorValue] = useState(initColor);

  const handleClose = () => {
    onClose(colorValue.hex);
  };

  return (
    <Dialog onClose={handleClose} open={open}>
      <SketchPicker
        onChange={setColorValue}
        onCancel={handleClose}
        color={colorValue}
        disableAlpha
        presetColors={['#D0021B', '#F5A623', '#F8E71C', '#8B572A', '#7ED321', '#417505',
          '#BD10E0', '#9013FE', '#4A90E2', '#50E3C2', '#B8E986', '#000000',
          '#4A4A4A', '#9B9B9B', '#FFFFFF']}
      />
    </Dialog>
  );
}

SimpleDialog.propTypes = {
  onClose: PropTypes.func.isRequired,
  open: PropTypes.bool.isRequired,
  initColor: PropTypes.string.isRequired,
};

export default function ValueColorItem({name, value, onChange}) {
  const [open, setOpen] = useState(false);
  const [colorValue, setColorValue] = useState(value);

  const handleClickOpen = () => {
    setOpen(true);
  };

  const handleClose = (valueOnClose) => {
    setOpen(false);
    console.log("valueOnClose", valueOnClose);
    if (valueOnClose) {
      setColorValue(valueOnClose);
      onChange({
        target: {
          name: name,
          value: valueOnClose,
          type: 'color'
        }
      });
    }
  };

  return (
    <div
      key={name}
      className="input-button"
    >
      <Button variant="outlined" onClick={handleClickOpen}>
        <div
          style={{
            backgroundColor: colorValue,
            width: "20px",
            height: "20px",
            border: "1px solid #BBB",
            borderRadius: "2pt",
            marginRight: "3pt",
          }}
          />
          {colorValue}
      </Button>
      <SimpleDialog
        initColor={colorValue}
        open={open}
        onClose={handleClose}
      />
    </div>
  );
}

ValueColorItem.propTypes = {
  name: PropTypes.string.isRequired,
  value: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
};
