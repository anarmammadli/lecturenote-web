const { app, BrowserWindow, ipcMain, dialog, desktopCapturer, session } = require("electron");
const fs = require("fs");
const path = require("path");

function setupScreenRecordingPermissions() {
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    const allowed = ["media", "display-capture"];
    callback(allowed.includes(permission));
  });

  session.defaultSession.setDisplayMediaRequestHandler((request, callback) => {
    desktopCapturer.getSources({
      types: ["screen", "window"],
      thumbnailSize: { width: 320, height: 180 }
    }).then((sources) => {
      if (!sources || sources.length === 0) {
        callback({});
        return;
      }

      const screenSource =
        sources.find(source => source.name.toLowerCase().includes("screen")) ||
        sources[0];

      if (process.platform === "win32") {
        callback({
          video: screenSource,
          audio: "loopback"
        });
      } else {
        callback({
          video: screenSource
        });
      }
    }).catch(() => {
      callback({});
    });
  }, {
    useSystemPicker: true
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1320,
    height: 860,
    minWidth: 1050,
    minHeight: 720,
    title: "LectureNote Studio",
    backgroundColor: "#0b1020",
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  win.loadFile(path.join(__dirname, "index.html"));
}

ipcMain.handle("choose-media", async () => {
  const result = await dialog.showOpenDialog({
    title: "Choose lecture audio or video",
    properties: ["openFile"],
    filters: [
      {
        name: "Audio / Video Files",
        extensions: [
          "mp3", "wav", "m4a", "aac", "flac", "ogg", "opus", "wma",
          "mp4", "mov", "mkv", "webm", "avi", "m4v", "wmv"
        ]
      },
      { name: "All Files", extensions: ["*"] }
    ]
  });

  if (result.canceled || result.filePaths.length === 0) return null;
  return result.filePaths[0];
});

ipcMain.handle("save-recording", async (_, bufferArray) => {
  const recordingsDir = path.join(__dirname, "recordings");

  if (!fs.existsSync(recordingsDir)) {
    fs.mkdirSync(recordingsDir, { recursive: true });
  }

  const fileName = `lecture-recording-${Date.now()}.webm`;
  const filePath = path.join(recordingsDir, fileName);

  fs.writeFileSync(filePath, Buffer.from(bufferArray));
  return filePath;
});

ipcMain.handle("save-transcript", async (_, payload) => {
  const defaultName = payload.defaultName || "transcript.txt";

  const result = await dialog.showSaveDialog({
    title: "Save transcript",
    defaultPath: defaultName,
    filters: [
      { name: "Text File", extensions: ["txt"] },
      { name: "JSON File", extensions: ["json"] }
    ]
  });

  if (result.canceled || !result.filePath) return null;

  fs.writeFileSync(result.filePath, payload.content, "utf8");
  return result.filePath;
});

app.whenReady().then(() => {
  setupScreenRecordingPermissions();
  createWindow();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
