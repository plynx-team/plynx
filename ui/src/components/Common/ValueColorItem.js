import * as React from 'react';
import Button from '@mui/material/Button';
import Avatar from '@mui/material/Avatar';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemAvatar from '@mui/material/ListItemAvatar';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import DialogTitle from '@mui/material/DialogTitle';
import Dialog from '@mui/material/Dialog';
import Typography from '@mui/material/Typography';
import { blue } from '@mui/material/colors';
import { SketchPicker, PhotoshopPicker } from 'react-color';
import { width } from '@mui/system';

const emails = ['username@gmail.com', 'user02@gmail.com'];

export interface SimpleDialogProps {
  open: boolean;
  selectedValue: string;
  onClose: (value: string) => void;
}

function SimpleDialog(props) {
  const { onClose, open, initColor } = props;
  const [colorValue, setColorValue] = React.useState(initColor);

  const handleClose = () => {
    onClose(colorValue.hex);
  };

  console.log("initColor", initColor);

  return (
    <Dialog onClose={handleClose} open={open}>
      <SketchPicker
        onChange={setColorValue}
        onCancel={handleClose}
        color={colorValue}
        disableAlpha={true}
        presetColors={['#D0021B', '#F5A623', '#F8E71C', '#8B572A', '#7ED321', '#417505',
    '#BD10E0', '#9013FE', '#4A90E2', '#50E3C2', '#B8E986', '#000000',
    '#4A4A4A', '#9B9B9B', '#FFFFFF']}
      />
    </Dialog>
  );
}

export default function ValueColorItem({name, value, onChange}) {
  const [open, setOpen] = React.useState(false);
  const [colorValue, setColorValue] = React.useState(value);

  const handleClickOpen = () => {
    setOpen(true);
  };

  const handleClose = (value) => {
    setOpen(false);
    console.log("value", value);
    if (value) {
      setColorValue(value);
      onChange({
        target: {
          name: name,
          value: value,
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
            "margin-right": "3pt",
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
