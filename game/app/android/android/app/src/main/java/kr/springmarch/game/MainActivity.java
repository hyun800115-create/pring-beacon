package kr.springmarch.game;

import android.os.Bundle;
import android.view.WindowManager;
import android.webkit.WebView;
import androidx.activity.OnBackPressedCallback;
import androidx.appcompat.app.AlertDialog;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;
import com.getcapacitor.BridgeActivity;

// 봄날의 행진 앱 몸통 (build_android.mjs 가 만든다 — 고치려면 그 파일을 고칠 것)
public class MainActivity extends BridgeActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // 노는 동안 화면이 꺼지지 않게
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        hideBars();
        // .glb(3D 모델) 파일 종류를 알려주는 길잡이
        if (bridge != null) bridge.setWebViewClient(new GameWebViewClient(bridge));
        // 뒤로 가기: 바로 꺼지지 않고 물어본다
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                new AlertDialog.Builder(MainActivity.this)
                    .setTitle("봄날의 행진")
                    .setMessage("게임을 끝낼까요?")
                    .setPositiveButton("끝내기", (d, w) -> signal("sm-app-pause", () -> finish()))   // 저장이 끝난 뒤에 닫는다
                    .setNegativeButton("계속하기", (d, w) -> hideBars())
                    .setOnCancelListener((d) -> hideBars())
                    .show();
            }
        });
    }

    // 위쪽 상태 막대·아래쪽 버튼 막대 숨기기 (화면 가장자리를 쓸어 넘기면 잠깐 보임)
    private void hideBars() {
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        WindowInsetsControllerCompat c = WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        c.hide(WindowInsetsCompat.Type.systemBars());
        c.setSystemBarsBehavior(WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
    }

    // 게임 화면에 신호 보내기 (소리 멈춤·저장 / 다시 켜기)
    private void signal(String name) {
        signal(name, null);
    }

    // after: 게임 쪽 처리(저장 등)가 끝난 뒤 할 일
    private void signal(String name, Runnable after) {
        if (bridge == null || bridge.getWebView() == null) {
            if (after != null) after.run();
            return;
        }
        bridge.getWebView().evaluateJavascript("try{window.dispatchEvent(new Event('" + name + "'))}catch(e){};1", after == null ? null : (v) -> after.run());
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) hideBars();
    }

    @Override
    public void onResume() {
        super.onResume();
        hideBars();
        if (bridge != null && bridge.getWebView() != null) bridge.getWebView().onResume();
        signal("sm-app-resume");
    }

    @Override
    public void onPause() {
        signal("sm-app-pause");
        WebView w = bridge != null ? bridge.getWebView() : null;
        if (w != null) w.onPause();
        super.onPause();
    }
}
