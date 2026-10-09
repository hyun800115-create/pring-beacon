package kr.springmarch.game;

import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import com.getcapacitor.Bridge;
import com.getcapacitor.BridgeWebViewClient;

// 앱 안 작은 서버가 모르는 파일 종류를 알려준다 (.glb = 3D 모델, .json, .ogg)
public class GameWebViewClient extends BridgeWebViewClient {

    public GameWebViewClient(Bridge bridge) {
        super(bridge);
    }

    @Override
    public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
        WebResourceResponse r = super.shouldInterceptRequest(view, request);
        if (r == null) return null;
        String p = request.getUrl().getPath();
        if (p == null) return r;
        if (p.endsWith(".glb")) r.setMimeType("model/gltf-binary");
        else if (p.endsWith(".json") && r.getMimeType() == null) r.setMimeType("application/json");
        else if (p.endsWith(".ogg") && r.getMimeType() == null) r.setMimeType("audio/ogg");
        return r;
    }
}
