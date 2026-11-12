#import <UIKit/UIKit.h>
#import <ios_system/ios_system.h>
#include <locale.h>

@interface PythonSmokeDelegate : UIResponder <UIApplicationDelegate, UIWindowSceneDelegate>
@property (strong, nonatomic) UIWindow *window;
@property (strong, nonatomic) UITextView *results;
@end
@implementation PythonSmokeDelegate
- (BOOL)application:(UIApplication *)application didFinishLaunchingWithOptions:(NSDictionary *)options { return YES; }
- (void)scene:(UIScene *)scene willConnectToSession:(UISceneSession *)session options:(UISceneConnectionOptions *)options {
 self.window = [[UIWindow alloc] initWithWindowScene:(UIWindowScene *)scene];
 UIViewController *controller = [UIViewController new];
 self.results = [[UITextView alloc] initWithFrame:self.window.bounds];
 self.results.editable = NO; self.results.text = @"Python runtime checks running…";
 self.results.accessibilityIdentifier = @"PythonSmokeResults";
 controller.view = self.results; self.window.rootViewController = controller; [self.window makeKeyAndVisible];
 dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
  NSString *app = NSBundle.mainBundle.bundlePath;
  NSString *documents = NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES).firstObject;
  NSString *output = [documents stringByAppendingPathComponent:@"python-results.txt"];
  initializeEnvironment(); joinMainThread = false; numPythonInterpreters = 2;
  setenv("APPDIR", app.UTF8String, 1); setenv("PYTHONHOME", [app stringByAppendingPathComponent:@"Library"].UTF8String, 1);
  setenv("PYTHONPYCACHEPREFIX", [documents stringByAppendingPathComponent:@"pycache"].UTF8String, 1);
  setenv("PYTHONUSERBASE", documents.UTF8String, 1); setenv("TERM", "xterm-256color", 1); setenv("SSL_CERT_FILE", [app stringByAppendingPathComponent:@"Library/lib/python3.13/site-packages/certifi/cacert.pem"].UTF8String, 1);
  setenv("LC_CTYPE", "UTF-8", 1); setlocale(LC_CTYPE, "UTF-8");
  NSString *path = [NSString stringWithFormat:@"%@/Library/bin:%@", app, documents]; setenv("PATH", path.UTF8String, 1);
  char *session = strdup("python-smoke"); ios_switchSession(session); ios_setContext(session);
  ios_setDirectoryURL([NSURL fileURLWithPath:documents]);
  NSArray *commands = @[
   @"python3 -c 'import sys, ssl, sqlite3, ctypes, lzma, hashlib, json; print(json.dumps({\"python\":sys.version,\"ssl\":ssl.OPENSSL_VERSION,\"sqlite\":sqlite3.sqlite_version,\"hash\":hashlib.sha256(b\"test\").hexdigest(),\"lzma\":lzma.decompress(lzma.compress(b\"ok\")).decode()}))'",
   @"pip --version",
   @"ipython --quick --no-banner -c 'print(\"IPYTHON_OK\")'",
   @"python3 -c 'import ssl, urllib.request; print(\"HTTPS_OK\", urllib.request.urlopen(\"https://pypi.org/simple/pip/\", timeout=30).status)'",
   @"pip install --disable-pip-version-check --no-compile --target ./pip-smoke six==1.17.0",
   @"python3 -c 'import sys; sys.path.insert(0, \"pip-smoke\"); import six; print(\"PIP_INSTALL_OK\", six.__version__)'",
   @"python3 -c 'import json, sqlite3; print(\"REPEAT_EXECUTION_OK\")'"
  ];
  int failures = 0;
  for (NSString *command in commands) {
   FILE *input = fopen("/dev/null", "r"); FILE *log = fopen(output.UTF8String, "a");
   ios_setStreams(input, log, log); thread_stdin = input; thread_stdout = log; thread_stderr = log;
   fprintf(log, "\nCOMMAND: %s\n", command.UTF8String); fflush(log);
   pid_t pid = ios_fork(); int status = ios_system(command.UTF8String); ios_waitpid(pid);
   if (!status) status = ios_getCommandStatus(); ios_releaseThreadId(pid);
   fprintf(log, "\nSTATUS: %d\n", status); fflush(log); fclose(log); fclose(input);
   if (status) failures++;
  }
  FILE *log = fopen(output.UTF8String, "a"); fprintf(log, "\n%s: %d failing checks\n", failures ? "FAIL" : "PASS", failures); fclose(log);
  NSString *text = [NSString stringWithContentsOfFile:output encoding:NSUTF8StringEncoding error:nil];
  dispatch_async(dispatch_get_main_queue(), ^{ self.results.text = text; });
 });
}
@end
int main(int argc, char *argv[]) {
 @autoreleasepool { return UIApplicationMain(argc, argv, nil, NSStringFromClass(PythonSmokeDelegate.class)); }
}
