package com.powerfin.pos.bridge.dispenser;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class DispenserStatusCache {

    private final Map<Integer, DispenserStatus> statusMap = new ConcurrentHashMap<>();

    public void update(DispenserStatus status) {
        statusMap.put(status.getDispenserId(), status);
    }

    public DispenserStatus get(int dispenserId) {
        return statusMap.get(dispenserId);
    }

    public List<DispenserStatus> getAll() {
        return List.copyOf(statusMap.values());
    }

    public Map<Integer, DispenserStatus> getMap() {
        return Map.copyOf(statusMap);
    }

    public static class DispenserStatus {
        private int dispenserId;
        private String status;
        private String subStatus;
        private int hoseCount;
        private double presetAmount;
        private String grade;
        private boolean payAlarm;
        private boolean connected;

        public DispenserStatus() {}

        public DispenserStatus(int dispenserId, String status, String subStatus,
                               int hoseCount, double presetAmount) {
            this.dispenserId = dispenserId;
            this.status = status;
            this.subStatus = subStatus;
            this.hoseCount = hoseCount;
            this.presetAmount = presetAmount;
            this.connected = true;
        }

        public int getDispenserId() { return dispenserId; }
        public void setDispenserId(int dispenserId) { this.dispenserId = dispenserId; }

        public String getStatus() { return status; }
        public void setStatus(String status) { this.status = status; }

        public String getSubStatus() { return subStatus; }
        public void setSubStatus(String subStatus) { this.subStatus = subStatus; }

        public int getHoseCount() { return hoseCount; }
        public void setHoseCount(int hoseCount) { this.hoseCount = hoseCount; }

        public double getPresetAmount() { return presetAmount; }
        public void setPresetAmount(double presetAmount) { this.presetAmount = presetAmount; }

        public String getGrade() { return grade; }
        public void setGrade(String grade) { this.grade = grade; }

        public boolean isPayAlarm() { return payAlarm; }
        public void setPayAlarm(boolean payAlarm) { this.payAlarm = payAlarm; }

        public boolean isConnected() { return connected; }
        public void setConnected(boolean connected) { this.connected = connected; }
    }
}
