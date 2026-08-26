using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace JarvisApp
{
    static class Program
    {
        private const string DEFAULT_URL = "https://jarvis-theo.vercel.app/cockpit";
        private const string APP_NAME = "JARVIS";

        [STAThread]
        static void Main(string[] args)
        {
            try
            {
                string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                string installDir = Path.Combine(localAppData, APP_NAME);
                if (!Directory.Exists(installDir))
                {
                    Directory.CreateDirectory(installDir);
                }

                string currentExe = Process.GetCurrentProcess().MainModule.FileName;
                string targetExe = Path.Combine(installDir, "JARVIS.exe");

                if (!string.Equals(currentExe, targetExe, StringComparison.OrdinalIgnoreCase))
                {
                    try
                    {
                        File.Copy(currentExe, targetExe, true);
                    }
                    catch { }
                }

                string desktopDir = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
                string startMenuDir = Environment.GetFolderPath(Environment.SpecialFolder.Programs);

                string desktopShortcut = Path.Combine(desktopDir, "JARVIS.lnk");
                string startMenuShortcut = Path.Combine(startMenuDir, "JARVIS.lnk");

                CreateWScriptShortcut(desktopShortcut, targetExe, "JARVIS - Central Pessoal de Inteligencia");
                CreateWScriptShortcut(startMenuShortcut, targetExe, "JARVIS - Central Pessoal de Inteligencia");

                string targetUrl = DEFAULT_URL;
                if (args.Length > 0 && !string.IsNullOrWhiteSpace(args[0]) && args[0].StartsWith("http", StringComparison.OrdinalIgnoreCase))
                {
                    targetUrl = args[0];
                }

                LaunchCockpit(targetUrl);
            }
            catch (Exception ex)
            {
                try
                {
                    Process.Start(new ProcessStartInfo(DEFAULT_URL) { UseShellExecute = true });
                }
                catch
                {
                    MessageBox.Show("Nao foi possivel iniciar o JARVIS: " + ex.Message, APP_NAME, MessageBoxButtons.OK, MessageBoxIcon.Information);
                }
            }
        }

        private static void LaunchCockpit(string url)
        {
            string edge = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), @"Microsoft\Edge\Application\msedge.exe");
            if (!File.Exists(edge))
            {
                edge = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), @"Microsoft\Edge\Application\msedge.exe");
            }

            if (File.Exists(edge))
            {
                try
                {
                    Process.Start(new ProcessStartInfo(edge, "--app=\"" + url + "\"") { UseShellExecute = false });
                    return;
                }
                catch { }
            }

            string chrome = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), @"Google\Chrome\Application\chrome.exe");
            if (!File.Exists(chrome))
            {
                chrome = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), @"Google\Chrome\Application\chrome.exe");
            }

            if (File.Exists(chrome))
            {
                try
                {
                    Process.Start(new ProcessStartInfo(chrome, "--app=\"" + url + "\"") { UseShellExecute = false });
                    return;
                }
                catch { }
            }

            Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
        }

        private static void CreateWScriptShortcut(string shortcutPath, string targetExePath, string description)
        {
            try
            {
                Type shellType = Type.GetTypeFromProgID("WScript.Shell");
                if (shellType != null)
                {
                    dynamic shell = Activator.CreateInstance(shellType);
                    dynamic shortcut = shell.CreateShortcut(shortcutPath);
                    shortcut.TargetPath = targetExePath;
                    shortcut.WorkingDirectory = Path.GetDirectoryName(targetExePath);
                    shortcut.Description = description;
                    shortcut.IconLocation = targetExePath + ",0";
                    shortcut.Save();
                }
            }
            catch { }
        }
    }
}
