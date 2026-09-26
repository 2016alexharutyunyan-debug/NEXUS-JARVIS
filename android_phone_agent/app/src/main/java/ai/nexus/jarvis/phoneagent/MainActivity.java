package ai.nexus.jarvis.phoneagent;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.net.Inet4Address;
import java.net.NetworkInterface;
import java.util.Collections;
import java.util.UUID;

public class MainActivity extends Activity {
    private static final int REQUEST_PERMISSIONS = 7;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        String token = getSharedPreferences("agent", MODE_PRIVATE).getString("token", "");
        if (token.isEmpty()) {
            token = UUID.randomUUID().toString().replace("-", "").substring(0, 12).toUpperCase();
            getSharedPreferences("agent", MODE_PRIVATE).edit().putString("token", token).apply();
        }
        AgentService.setToken(token);
        buildUi(token);
        requestPermissionsIfNeeded();
    }

    private void buildUi(String token) {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(44, 70, 44, 44);
        root.setBackgroundColor(Color.rgb(2, 10, 16));
        TextView title = label("JARVIS PHONE AGENT", 26, Color.rgb(125, 235, 255));
        TextView status = label("READY FOR SECURE LOCAL CONTROL", 14, Color.rgb(100, 180, 200));
        TextView ip = label("PHONE IP\n" + localIp() + ":8766", 22, Color.WHITE);
        TextView code = label("PAIRING CODE\n" + token, 22, Color.WHITE);
        TextView note = label("Keep this service running. JARVIS still asks for confirmation on the PC before every call or SMS.", 15, Color.LTGRAY);
        Button start = new Button(this);
        start.setText("START PHONE AGENT");
        start.setOnClickListener(v -> {
            requestPermissionsIfNeeded();
            startForegroundService(new Intent(this, AgentService.class));
            status.setText("ACTIVE • YOU MAY CLOSE THIS SCREEN");
        });
        Button battery = new Button(this);
        battery.setText("OPEN BATTERY SETTINGS");
        battery.setOnClickListener(v -> startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)));
        root.addView(title); root.addView(status); root.addView(ip); root.addView(code); root.addView(note); root.addView(start); root.addView(battery);
        setContentView(root);
    }

    private TextView label(String text, int size, int color) {
        TextView view = new TextView(this);
        view.setText(text); view.setTextSize(size); view.setTextColor(color); view.setGravity(Gravity.CENTER_HORIZONTAL);
        view.setPadding(0, 20, 0, 20); return view;
    }

    private void requestPermissionsIfNeeded() {
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            requestPermissions(new String[]{Manifest.permission.SEND_SMS, Manifest.permission.CALL_PHONE, Manifest.permission.POST_NOTIFICATIONS}, REQUEST_PERMISSIONS);
        } else {
            requestPermissions(new String[]{Manifest.permission.SEND_SMS, Manifest.permission.CALL_PHONE}, REQUEST_PERMISSIONS);
        }
    }

    private String localIp() {
        try {
            for (NetworkInterface nic : Collections.list(NetworkInterface.getNetworkInterfaces()))
                for (java.net.InetAddress address : Collections.list(nic.getInetAddresses()))
                    if (!address.isLoopbackAddress() && address instanceof Inet4Address) return address.getHostAddress();
        } catch (Exception ignored) { }
        return "Connect to Wi-Fi";
    }
}
