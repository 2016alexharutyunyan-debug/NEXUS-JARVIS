package ai.nexus.jarvis.phoneagent;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.os.IBinder;
import android.telephony.SmsManager;
import android.telecom.TelecomManager;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Set;

public class AgentService extends Service {
    private static final Set<String> EMERGENCY = new HashSet<>(java.util.Arrays.asList("101", "102", "103", "104", "112", "911"));
    private static volatile String token = "";
    private volatile boolean running;
    private ServerSocket server;

    public static void setToken(String value) { token = value; }

    @Override public void onCreate() {
        super.onCreate();
        if (token.isEmpty()) token = getSharedPreferences("agent", MODE_PRIVATE).getString("token", "");
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel("jarvis_agent", "JARVIS Phone Agent", NotificationManager.IMPORTANCE_LOW));
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE);
        Notification notification = new Notification.Builder(this, "jarvis_agent")
                .setContentTitle("JARVIS Phone Agent active")
                .setContentText("Waiting for confirmed local commands")
                .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
                .setContentIntent(open).build();
        startForeground(8766, notification);
        running = true;
        new Thread(this::serve, "jarvis-phone-agent").start();
    }

    private void serve() {
        try {
            server = new ServerSocket(8766);
            while (running) handle(server.accept());
        } catch (Exception ignored) { }
    }

    private void handle(Socket socket) {
        try (socket) {
            socket.setSoTimeout(5000);
            BufferedReader reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
            String first = reader.readLine();
            String path = first == null ? "" : first.split(" ")[1];
            int length = 0; String suppliedToken = ""; String line;
            while ((line = reader.readLine()) != null && !line.isEmpty()) {
                int split = line.indexOf(':'); if (split < 0) continue;
                String name = line.substring(0, split).trim(); String value = line.substring(split + 1).trim();
                if (name.equalsIgnoreCase("Content-Length")) length = Integer.parseInt(value);
                if (name.equalsIgnoreCase("X-JARVIS-TOKEN")) suppliedToken = value;
            }
            char[] body = new char[Math.min(length, 8192)]; int read = 0;
            while (read < body.length) { int count = reader.read(body, read, body.length - read); if (count < 0) break; read += count; }
            if (token.isEmpty() || !constantTimeEquals(token, suppliedToken)) { respond(socket, 403, false, "Invalid pairing code."); return; }
            JSONObject data = new JSONObject(new String(body, 0, read));
            String number = data.optString("number").replaceAll("[^0-9+]", "");
            String digits = number.replaceAll("\\D", "");
            if (digits.length() < 3 || digits.length() > 16 || EMERGENCY.contains(digits)) { respond(socket, 400, false, "Blocked or invalid phone number."); return; }
            try {
                if (path.equals("/sms")) sendSms(number, data.optString("message"));
                else if (path.equals("/call")) call(number);
                else { respond(socket, 404, false, "Unknown action."); return; }
                respond(socket, 200, true, path.equals("/sms") ? "SMS sent." : "Call started.");
            } catch (Exception actionError) {
                String detail = actionError.getMessage();
                respond(socket, 500, false, detail == null ? "Phone action failed." : detail);
            }
        } catch (Exception ignored) { }
    }

    private void sendSms(String number, String message) throws Exception {
        if (checkSelfPermission(Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED) throw new SecurityException("SMS permission missing");
        if (message.trim().isEmpty()) throw new IllegalArgumentException("Message is empty");
        SmsManager manager = SmsManager.getDefault();
        java.util.ArrayList<String> parts = manager.divideMessage(message);
        manager.sendMultipartTextMessage(number, null, parts, null, null);
    }

    private void call(String number) {
        if (checkSelfPermission(Manifest.permission.CALL_PHONE) != PackageManager.PERMISSION_GRANTED) throw new SecurityException("Call permission missing");
        TelecomManager telecom = (TelecomManager) getSystemService(TELECOM_SERVICE);
        telecom.placeCall(Uri.parse("tel:" + number), new Bundle());
    }

    private boolean constantTimeEquals(String a, String b) {
        if (a.length() != b.length()) return false; int diff = 0;
        for (int i = 0; i < a.length(); i++) diff |= a.charAt(i) ^ b.charAt(i); return diff == 0;
    }

    private void respond(Socket socket, int code, boolean ok, String message) throws Exception {
        byte[] body = new JSONObject().put("ok", ok).put(ok ? "message" : "error", message).toString().getBytes(StandardCharsets.UTF_8);
        OutputStream out = socket.getOutputStream();
        out.write(("HTTP/1.1 " + code + " OK\r\nContent-Type: application/json\r\nContent-Length: " + body.length + "\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.US_ASCII));
        out.write(body); out.flush();
    }

    @Override public void onDestroy() { running = false; try { if (server != null) server.close(); } catch (Exception ignored) { } super.onDestroy(); }
    @Override public IBinder onBind(Intent intent) { return null; }
}
