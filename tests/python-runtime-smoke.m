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
   @"python3 -c 'from Crypto.Cipher import AES; from Crypto.Hash import SHA256; from Crypto.PublicKey import RSA; key=RSA.generate(1024); assert RSA.import_key(key.export_key()).n==key.n; a=AES.new(bytes(16),AES.MODE_ECB); assert a.decrypt(a.encrypt(bytes(16)))==bytes(16); assert len(SHA256.new(b\"test\").digest())==32; print(\"CRYPTO_OK\")'",
   @"python3 -c 'from Cryptodome.Cipher import AES; from Cryptodome.Hash import SHA256; from Cryptodome.PublicKey import RSA; key=RSA.generate(1024); assert RSA.import_key(key.export_key()).n==key.n; a=AES.new(bytes(16),AES.MODE_ECB); assert a.decrypt(a.encrypt(bytes(16)))==bytes(16); assert len(SHA256.new(b\"test\").digest())==32; print(\"CRYPTODOME_OK\")'",
   @"python3 -c 'from Crypto.Cipher import AES; from Crypto.Hash import SHA256; from Crypto.PublicKey import RSA; key=RSA.generate(1024); assert RSA.import_key(key.export_key()).n==key.n; a=AES.new(bytes(16),AES.MODE_ECB); assert a.decrypt(a.encrypt(bytes(16)))==bytes(16); assert len(SHA256.new(b\"test\").digest())==32; print(\"CRYPTO_OK\")'",
   @"python3 -c 'import scipy, numpy as np; from scipy import linalg, integrate, special, optimize, sparse, stats; assert np.allclose(linalg.solve([[3.,1.],[1.,2.]],[9.,8.]),[2.,3.]); assert abs(integrate.quad(lambda x:x*x,0,1)[0]-1/3)<1e-10; assert special.erf(0)==0; assert abs(stats.norm.cdf(0)-0.5)<1e-10; r=optimize.linprog([1.,1.],bounds=[(1,None),(2,None)],method=\"highs\"); assert r.success and np.allclose(r.x,[1,2]); assert abs(sparse.linalg.eigs(sparse.diags([1.,2.,3.,4.]),k=1,which=\"LM\")[0][0]-4)<1e-6; print(\"SCIPY_OK\", scipy.__version__)'",
   @"python3 -c 'import numpy as np; from scipy.sparse.linalg import svds; ds=[np.float32,np.float64,np.complex64,np.complex128]; values=[svds(np.diag(np.array([1,2,3,4],dtype=d)),k=2,solver=\"propack\",return_singular_vectors=False) for d in ds]; assert all(np.allclose(x,[3,4],atol=1e-4) for x in values); print(\"SCIPY_PROPACK_TYPES_OK\")'",
   @"python3 -c 'from scipy.integrate import quad; from scipy.optimize import minimize; assert abs(quad(lambda x:x*x,0,1)[0]-1/3)<1e-10; r=minimize(lambda x:(x[0]-3)**2,[0.]); assert r.success; print(\"SCIPY_REPEAT_OK\")'",

   @"python3 -c 'import kiwisolver as k; x=k.Variable(\"x\"); s=k.Solver(); s.addConstraint(x==42); s.updateVariables(); assert x.value()==42; print(\"KIWISOLVER_OK\")'",

   @"python3 -c 'import numpy as np; from PIL import Image; from cryptography.fernet import Fernet; assert np.linalg.det(np.eye(3))==1; assert Image.new(\"L\",(2,2),7).getpixel((0,0))==7; f=Fernet(Fernet.generate_key()); assert f.decrypt(f.encrypt(b\"reuse\"))==b\"reuse\"; print(\"NATIVE_REENTRY_1\")'",
   @"python3 -c 'import numpy as np; from PIL import Image; from cryptography.fernet import Fernet; assert np.arange(9).sum()==36; assert Image.new(\"L\",(2,2),7).getpixel((0,0))==7; f=Fernet(Fernet.generate_key()); assert f.decrypt(f.encrypt(b\"reuse\"))==b\"reuse\"; print(\"NATIVE_REENTRY_2\")'",
   @"python3 -c 'import numpy as np; from PIL import Image; from cryptography.fernet import Fernet; assert np.linalg.det(np.eye(3))==1; assert Image.new(\"L\",(2,2),7).getpixel((0,0))==7; f=Fernet(Fernet.generate_key()); assert f.decrypt(f.encrypt(b\"reuse\"))==b\"reuse\"; print(\"NATIVE_REENTRY_3\")'",

   @"python3 -c 'from PIL import Image, ImageFont, ImageShow; from io import BytesIO; im=Image.new(\"RGB\",(13,7),(10,20,30)); out=BytesIO(); im.save(out,format=\"PNG\"); out.seek(0); assert Image.open(out).getpixel((0,0))==(10,20,30); assert ImageFont.load_default().getbbox(\"Hello\")[2]>0; print(\"PILLOW_OK\")'",
   @"python3 -c 'from PIL import Image; from io import BytesIO; b=BytesIO(); Image.new(\"RGB\",(20,20),\"red\").save(b,format=\"JPEG\"); b.seek(0); assert Image.open(b).size==(20,20); print(\"PILLOW_REPEAT_OK\")'",

   @"python3 -c 'import numpy as np; a=np.array([[3.,1.],[1.,2.]]); assert np.allclose(np.linalg.solve(a,[9.,8.]),[2.,3.]); assert np.allclose(np.fft.rfft([0,1,2,3]),[6,-2+2j,-2]); print(\"NUMPY_OK\", np.__version__)'",
   @"python3 -c 'import numpy as np; x=np.random.default_rng(7).normal(size=100); assert np.isfinite(x).all(); print(\"NUMPY_REPEAT_OK\", float(x.mean()))'",

   @"python3 -c 'import cryptography; from cryptography.fernet import Fernet; f=Fernet(Fernet.generate_key()); assert f.decrypt(f.encrypt(b\"crypto works\")) == b\"crypto works\"; print(\"CRYPTOGRAPHY_OK\", cryptography.__version__)'",
   @"python3 -c 'from cryptography.fernet import Fernet; f=Fernet(Fernet.generate_key()); assert f.decrypt(f.encrypt(b\"repeat\")) == b\"repeat\"; print(\"CRYPTOGRAPHY_REPEAT_OK\")'",

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
