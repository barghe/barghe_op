bool HKG_forwarding_enabled = 1;
int HKG_LKAS_forwarded = 0;
int HKG_ClU11_forwarded = 0;
int HKG_OP_LKAS_live = 0;
int HKG_OP_ClU11_live = 0;

void default_rx_hook(CAN_FIFOMailBox_TypeDef *to_push) {
  UNUSED(to_push);
  
}

int default_ign_hook(void) {
  return -1; // use GPIO to determine ignition
}

// *** no output safety mode ***

static void nooutput_init(int16_t param) {
  UNUSED(param);
  controls_allowed = 0;
}

static int nooutput_tx_hook(CAN_FIFOMailBox_TypeDef *to_send) {
  int addr = GET_ADDR(to_send);
  if (addr == 832) {
    if (HKG_LKAS_forwarded < 1) {
      HKG_OP_LKAS_live = 20;
    }
    else {
      HKG_LKAS_forwarded -= 1;
    }
  }
  if (addr == 1265) {
    if (HKG_ClU11_forwarded < 1) {
      HKG_OP_ClU11_live = 20;
    }
    else {
      HKG_ClU11_forwarded -= 1;
    }
  }
  return 1;
}

static int nooutput_tx_lin_hook(int lin_num, uint8_t *data, int len) {
  UNUSED(lin_num);
  UNUSED(data);
  UNUSED(len);
  return false;
}

 static int default_fwd_hook(int bus_num, CAN_FIFOMailBox_TypeDef *to_fwd) {
  int addr = GET_ADDR(to_fwd);
  int bus_fwd = -1;

  if ((addr == 832) && (bus_num == 0)) {
    HKG_forwarding_enabled = 0;
  }

  if (HKG_forwarding_enabled) {
    if (bus_num == 0) {
      if ((addr != 1265) || (HKG_OP_ClU11_live < 1)) {
        if (addr == 1265) {HKG_ClU11_forwarded = 2;}
        bus_fwd = 12;
      } else {
        HKG_OP_ClU11_live -= 1;
        HKG_ClU11_forwarded = 1;
        bus_fwd = 2;
      }
    }
    if (bus_num == 1) {
      bus_fwd = 20;
    }
    if (bus_num == 2) {
      if (addr != 832) {
        bus_fwd = 10;
      }
      else if (HKG_OP_LKAS_live < 1) {
        HKG_LKAS_forwarded = 2;
        bus_fwd = 10;
      }
      else {
        HKG_OP_LKAS_live -= 1;
      }
    }
  } else {
    if (bus_num == 0) {
      if (addr == 1265) {HKG_ClU11_forwarded = 1;}
      bus_fwd = 1;
    }
    if (bus_num == 1) {
      bus_fwd = 0;
    }
  }
  return bus_fwd;
}

const safety_hooks nooutput_hooks = {
  .init = nooutput_init,
  .rx = default_rx_hook,
  .tx = nooutput_tx_hook,
  .tx_lin = nooutput_tx_lin_hook,
  .ignition = default_ign_hook,
  .fwd = default_fwd_hook,
};

// *** all output safety mode ***

static void alloutput_init(int16_t param) {
  UNUSED(param);
  controls_allowed = 1;
}

static int alloutput_tx_hook(CAN_FIFOMailBox_TypeDef *to_send) {
  int addr = GET_ADDR(to_send);
  if (addr == 832) {
    if (HKG_LKAS_forwarded < 1) {
      HKG_OP_LKAS_live = 20;
    }
    else {
      HKG_LKAS_forwarded -= 1;
    }
  }
  if (addr == 1265) {
    if (HKG_ClU11_forwarded < 1) {
      HKG_OP_ClU11_live = 20;
    }
    else {
      HKG_ClU11_forwarded -= 1;
    }
  }
  return 1;
}

static int alloutput_tx_lin_hook(int lin_num, uint8_t *data, int len) {
  UNUSED(lin_num);
  UNUSED(data);
  UNUSED(len);
  return 1;
}

const safety_hooks alloutput_hooks = {
  .init = alloutput_init,
  .rx = default_rx_hook,
  .tx = alloutput_tx_hook,
  .tx_lin = alloutput_tx_lin_hook,
  .ignition = default_ign_hook,
  .fwd = default_fwd_hook,
};
