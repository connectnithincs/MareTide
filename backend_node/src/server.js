import express from "express";
import cors from "cors";
import http from "http";
import { WebSocketServer, WebSocket } from "ws";
import axios from "axios";

const app = express();
const port = 8000;

app.use(cors({
  origin: true,
  credentials: true
}));
app.use(express.json());

const server = http.createServer(app);
const wss = new WebSocketServer({ noServer: true });

// --- WS UPGRADE HANDSHAKE ---
server.on("upgrade", (request, socket, head) => {
  const { pathname } = new URL(request.url, `http://${request.headers.host}`);
  if (pathname === "/ws/telemetry") {
    wss.handleUpgrade(request, socket, head, (ws) => {
      wss.emit("connection", ws, request);
    });
  } else {
    socket.destroy();
  }
});

wss.on("connection", (ws) => {
  console.log("Client connected to telemetry WebSocket");
  ws.on("close", () => {
    console.log("Client disconnected");
  });
});

// --- TELEMETRY BROADCASTER LOOP ---
// Polls the sidecar state 10 times a second and broadcasts to any open WebSockets
setInterval(async () => {
  if (wss.clients.size > 0) {
    try {
      const res = await axios.get("http://localhost:8001/api/vessel-state", { timeout: 150 });
      const payload = JSON.stringify(res.data);
      wss.clients.forEach((client) => {
        if (client.readyState === WebSocket.OPEN) {
          client.send(payload);
        }
      });
    } catch (err) {
      // Suppress sidecar offline errors to prevent log spamming
    }
  }
}, 100);

// --- API PROXY MIDDLEWARE & ROUTES ---

// Helper function to forward request to target URL
const forwardTo = (targetBaseUrl) => async (req, res) => {
  const url = `${targetBaseUrl}${req.originalUrl}`;
  try {
    const config = {
      method: req.method,
      url: url,
      data: req.body,
      headers: { ...req.headers }
    };
    // Delete host, origin, and payload-length headers to prevent proxy validation failures
    delete config.headers.host;
    delete config.headers.origin;
    delete config.headers['content-length'];
    delete config.headers['Content-Length'];
    delete config.headers['connection'];
    delete config.headers['Connection'];
    delete config.headers['transfer-encoding'];
    delete config.headers['Transfer-Encoding'];

    const response = await axios(config);
    return res.status(response.status).json(response.data);
  } catch (error) {
    if (error.response) {
      return res.status(error.response.status).json(error.response.data);
    }
    return res.status(500).json({ success: false, message: "Target service connection failure", error: error.message });
  }
};

const SIDECAR_URL = "http://localhost:8001";
const FLASK_URL = "http://localhost:5000";

// Auth Handshake: Single-use token validation via Flask Auth Server
app.get("/api/auth/exchange", async (req, res) => {
  const token = req.query.token;
  if (!token) {
    return res.status(400).json({ success: false, message: "Token parameter missing" });
  }
  try {
    const response = await axios.get(`${FLASK_URL}/api/validate_token?token=${token}`);
    return res.json(response.data);
  } catch (error) {
    if (error.response) {
      return res.status(error.response.status).json(error.response.data);
    }
    return res.status(500).json({ success: false, message: "Auth server offline", error: error.message });
  }
});

// Auth Guard: Proxy active session verification to Flask Auth Server
app.get("/api/auth/session", async (req, res) => {
  try {
    const response = await axios.get(`${FLASK_URL}/api/check_session`, {
      headers: { cookie: req.headers.cookie || "" }
    });
    return res.json(response.data);
  } catch (error) {
    return res.status(500).json({ authenticated: false, error: error.message });
  }
});

// Proxy all other calculations, telemetry, loading flow controls and logs to FastAPI Sidecar
app.all("/api/vessel-state", forwardTo(SIDECAR_URL));
app.all("/api/ballast/*", forwardTo(SIDECAR_URL));
app.all("/api/recommendations", forwardTo(SIDECAR_URL));
app.all("/api/deck-plan", forwardTo(SIDECAR_URL));
app.all("/api/reports/*", forwardTo(SIDECAR_URL));
app.all("/api/telemetry/*", forwardTo(SIDECAR_URL));
app.all("/api/vision/*", forwardTo(SIDECAR_URL));
app.all("/api/voyage/*", forwardTo(SIDECAR_URL));

// Server Boot
server.listen(port, "0.0.0.0", () => {
  console.log(`Node.js API Gateway listening on http://localhost:${port}`);
});
