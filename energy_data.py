def get_energy_data():
    # ILLUSTRATIVE DEMO DATA ONLY — not measured VTU electricity data.
    return {
        "hours": ["06:00", "07:00", "08:00", "09:00", "10:00", "11:00",
                  "12:00", "13:00", "14:00", "15:00", "16:00", "17:00",
                  "18:00", "19:00", "20:00", "21:00"],
        "solar": [1, 2, 4, 8, 14, 18, 20, 21, 19, 16, 12, 8, 4, 1, 0, 0],
        "demand": [4, 5, 7, 9, 11, 14, 16, 15, 14, 13, 12, 11, 12, 14, 10, 7],
        "battery": [35, 37, 40, 45, 53, 64, 75, 85, 92, 96, 91, 83, 72, 60, 52, 46],
        "grid": [3, 3, 3, 1, 0, 0, 0, 0, 0, 0, 0, 3, 8, 13, 10, 7],
        "price": [5.2, 5.2, 5.4, 5.8, 6.0, 6.2, 6.2, 6.2,
                  6.0, 6.0, 6.5, 7.0, 8.2, 8.5, 8.0, 7.0],
        "unit": {"power": "kW", "battery": "%", "price": "₹/kWh"},
        "data_type": "SIMULATED — illustrative values, not VTU meter readings"
    }
