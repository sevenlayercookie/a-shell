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
  FILE *reset = fopen(output.UTF8String, "w"); if (reset) fclose(reset);
  initializeEnvironment(); joinMainThread = false; numPythonInterpreters = 2;
  setenv("APPDIR", app.UTF8String, 1); setenv("PYTHONHOME", [app stringByAppendingPathComponent:@"Library"].UTF8String, 1);
  setenv("PYTHONPYCACHEPREFIX", [documents stringByAppendingPathComponent:@"pycache"].UTF8String, 1);
  setenv("PYTHONUSERBASE", documents.UTF8String, 1); setenv("TERM", "xterm-256color", 1); setenv("SSL_CERT_FILE", [app stringByAppendingPathComponent:@"Library/lib/python3.13/site-packages/certifi/cacert.pem"].UTF8String, 1);
  setenv("LC_CTYPE", "UTF-8", 1); setlocale(LC_CTYPE, "UTF-8");
  NSString *path = [NSString stringWithFormat:@"%@/Library/bin:%@", app, documents]; setenv("PATH", path.UTF8String, 1);
  char *session = strdup("python-smoke"); ios_switchSession(session); ios_setContext(session);
  ios_setDirectoryURL([NSURL fileURLWithPath:documents]);
  NSArray *commands = @[
   @"python3 -c 'import zmq; assert zmq.has(\"curve\"); assert \"cffi\" in zmq.backend.Socket.__module__; ctx=zmq.Context(); server=ctx.socket(zmq.PAIR); client=ctx.socket(zmq.PAIR); server.rcvtimeo=5000; client.rcvtimeo=5000; spub,ssec=zmq.curve_keypair(); server.curve_publickey=spub; server.curve_secretkey=ssec; server.curve_server=True; client.curve_publickey,client.curve_secretkey=zmq.curve_keypair(); client.curve_serverkey=spub; port=server.bind_to_random_port(\"tcp://127.0.0.1\"); client.connect(\"tcp://127.0.0.1:\"+str(port)); client.send(b\"secure roundtrip\"); assert server.recv()==b\"secure roundtrip\"; server.send_multipart([b\"part1\",b\"part2\"]); assert client.recv_multipart()==[b\"part1\",b\"part2\"]; client.close(0); server.close(0); ctx.term(); print(\"PYZMQ_CURVE_REENTRY_1_OK\",zmq.pyzmq_version(),zmq.zmq_version())'",
   @"python3 -c 'import zmq; assert zmq.has(\"curve\"); assert \"cffi\" in zmq.backend.Socket.__module__; ctx=zmq.Context(); server=ctx.socket(zmq.PAIR); client=ctx.socket(zmq.PAIR); server.rcvtimeo=5000; client.rcvtimeo=5000; spub,ssec=zmq.curve_keypair(); server.curve_publickey=spub; server.curve_secretkey=ssec; server.curve_server=True; client.curve_publickey,client.curve_secretkey=zmq.curve_keypair(); client.curve_serverkey=spub; port=server.bind_to_random_port(\"tcp://127.0.0.1\"); client.connect(\"tcp://127.0.0.1:\"+str(port)); client.send(b\"secure roundtrip\"); assert server.recv()==b\"secure roundtrip\"; server.send_multipart([b\"part1\",b\"part2\"]); assert client.recv_multipart()==[b\"part1\",b\"part2\"]; client.close(0); server.close(0); ctx.term(); print(\"PYZMQ_CURVE_REENTRY_2_OK\",zmq.pyzmq_version(),zmq.zmq_version())'",
   @"python3 -c 'import zmq; assert zmq.has(\"curve\"); assert \"cffi\" in zmq.backend.Socket.__module__; ctx=zmq.Context(); server=ctx.socket(zmq.PAIR); client=ctx.socket(zmq.PAIR); server.rcvtimeo=5000; client.rcvtimeo=5000; spub,ssec=zmq.curve_keypair(); server.curve_publickey=spub; server.curve_secretkey=ssec; server.curve_server=True; client.curve_publickey,client.curve_secretkey=zmq.curve_keypair(); client.curve_serverkey=spub; port=server.bind_to_random_port(\"tcp://127.0.0.1\"); client.connect(\"tcp://127.0.0.1:\"+str(port)); client.send(b\"secure roundtrip\"); assert server.recv()==b\"secure roundtrip\"; server.send_multipart([b\"part1\",b\"part2\"]); assert client.recv_multipart()==[b\"part1\",b\"part2\"]; client.close(0); server.close(0); ctx.term(); print(\"PYZMQ_CURVE_REENTRY_3_OK\",zmq.pyzmq_version(),zmq.zmq_version())'",
   @"python3 -c 'from argon2 import PasswordHasher; from argon2.low_level import hash_secret_raw, Type; p=PasswordHasher(time_cost=1,memory_cost=1024,parallelism=1); h=p.hash(\"test-secret\"); assert p.verify(h,\"test-secret\"); assert not p.check_needs_rehash(h); raw=hash_secret_raw(b\"secret\",b\"somesalt\",time_cost=1,memory_cost=1024,parallelism=1,hash_len=32,type=Type.ID); assert len(raw)==32; print(\"ARGON2_REENTRY_1_OK\")'",
   @"python3 -c 'from argon2 import PasswordHasher; from argon2.low_level import hash_secret_raw, Type; p=PasswordHasher(time_cost=1,memory_cost=1024,parallelism=1); h=p.hash(\"test-secret\"); assert p.verify(h,\"test-secret\"); assert not p.check_needs_rehash(h); raw=hash_secret_raw(b\"secret\",b\"somesalt\",time_cost=1,memory_cost=1024,parallelism=1,hash_len=32,type=Type.ID); assert len(raw)==32; print(\"ARGON2_REENTRY_2_OK\")'",
   @"python3 -c 'from argon2 import PasswordHasher; from argon2.low_level import hash_secret_raw, Type; p=PasswordHasher(time_cost=1,memory_cost=1024,parallelism=1); h=p.hash(\"test-secret\"); assert p.verify(h,\"test-secret\"); assert not p.check_needs_rehash(h); raw=hash_secret_raw(b\"secret\",b\"somesalt\",time_cost=1,memory_cost=1024,parallelism=1,hash_len=32,type=Type.ID); assert len(raw)==32; print(\"ARGON2_REENTRY_3_OK\")'",
   @"python3 -c 'import psutil, os; p=psutil.Process(os.getpid()); assert p.pid==os.getpid(); assert psutil.cpu_count()>=1; assert psutil.virtual_memory().total>0; assert p.memory_info().rss>0; assert psutil.disk_usage(\".\").total>0; print(\"PSUTIL_REENTRY_1_OK\",psutil.__version__)'",
   @"python3 -c 'import psutil, os; p=psutil.Process(os.getpid()); assert p.pid==os.getpid(); assert psutil.cpu_count()>=1; assert psutil.virtual_memory().total>0; assert p.memory_info().rss>0; assert psutil.disk_usage(\".\").total>0; print(\"PSUTIL_REENTRY_2_OK\",psutil.__version__)'",
   @"python3 -c 'import psutil, os; p=psutil.Process(os.getpid()); assert p.pid==os.getpid(); assert psutil.cpu_count()>=1; assert psutil.virtual_memory().total>0; assert p.memory_info().rss>0; assert psutil.disk_usage(\".\").total>0; print(\"PSUTIL_REENTRY_3_OK\",psutil.__version__)'",
   @"wordcloud_cli --help",
   @"python3 -c 'from wordcloud import WordCloud; import numpy as np; from io import BytesIO; w=WordCloud(width=240,height=120,max_words=10,random_state=1).generate(\"alpha beta gamma alpha beta alpha\"); a=w.to_array(); assert a.shape==(120,240,3); assert w.words_[\"alpha\"]==1.0; assert np.unique(a.reshape(-1,3),axis=0).shape[0]>2; b=BytesIO(); w.to_image().save(b,format=\"PNG\"); assert b.getvalue().startswith(bytes([137,80,78,71])); print(\"WORDCLOUD_REENTRY_1_OK\")'",
   @"python3 -c 'from wordcloud import WordCloud; import numpy as np; from io import BytesIO; w=WordCloud(width=240,height=120,max_words=10,random_state=1).generate(\"alpha beta gamma alpha beta alpha\"); a=w.to_array(); assert a.shape==(120,240,3); assert w.words_[\"alpha\"]==1.0; assert np.unique(a.reshape(-1,3),axis=0).shape[0]>2; b=BytesIO(); w.to_image().save(b,format=\"PNG\"); assert b.getvalue().startswith(bytes([137,80,78,71])); print(\"WORDCLOUD_REENTRY_2_OK\")'",
   @"python3 -c 'from wordcloud import WordCloud; import numpy as np; from io import BytesIO; w=WordCloud(width=240,height=120,max_words=10,random_state=1).generate(\"alpha beta gamma alpha beta alpha\"); a=w.to_array(); assert a.shape==(120,240,3); assert w.words_[\"alpha\"]==1.0; assert np.unique(a.reshape(-1,3),axis=0).shape[0]>2; b=BytesIO(); w.to_image().save(b,format=\"PNG\"); assert b.getvalue().startswith(bytes([137,80,78,71])); print(\"WORDCLOUD_REENTRY_3_OK\")'",
   @"f2py -v",
   @"python3 -c 'import matplotlib; matplotlib.use(\"Agg\"); from matplotlib import pyplot as plt; from matplotlib.tri import Triangulation; import numpy as np; from io import BytesIO; tri=Triangulation([0,1,0,1],[0,0,1,1]); assert tri.triangles.shape==(2,3); assert tri.get_trifinder()(0.2,0.3)>=0; fig,ax=plt.subplots(); ax.imshow(np.array([[0.,1.],[1.,2.]])); ax.contour([[0.,1.],[1.,2.]]); ax.plot([0,1],[1,0]); ax.set_title(r\"Math $x^2$ and fonts\"); png=BytesIO(); fig.savefig(png,format=\"png\"); assert png.getvalue().startswith(bytes([137,80,78,71])); svg=BytesIO(); fig.savefig(svg,format=\"svg\"); assert b\"<svg\" in svg.getvalue(); pdf=BytesIO(); fig.savefig(pdf,format=\"pdf\"); assert pdf.getvalue().startswith(b\"%PDF\"); plt.close(fig); print(\"MATPLOTLIB_REENTRY_1_OK\",matplotlib.__version__)'",
   @"python3 -c 'import matplotlib; matplotlib.use(\"Agg\"); from matplotlib import pyplot as plt; from matplotlib.tri import Triangulation; import numpy as np; from io import BytesIO; tri=Triangulation([0,1,0,1],[0,0,1,1]); assert tri.triangles.shape==(2,3); assert tri.get_trifinder()(0.2,0.3)>=0; fig,ax=plt.subplots(); ax.imshow(np.array([[0.,1.],[1.,2.]])); ax.contour([[0.,1.],[1.,2.]]); ax.plot([0,1],[1,0]); ax.set_title(r\"Math $x^2$ and fonts\"); png=BytesIO(); fig.savefig(png,format=\"png\"); assert png.getvalue().startswith(bytes([137,80,78,71])); svg=BytesIO(); fig.savefig(svg,format=\"svg\"); assert b\"<svg\" in svg.getvalue(); pdf=BytesIO(); fig.savefig(pdf,format=\"pdf\"); assert pdf.getvalue().startswith(b\"%PDF\"); plt.close(fig); print(\"MATPLOTLIB_REENTRY_2_OK\",matplotlib.__version__)'",
   @"python3 -c 'import matplotlib; matplotlib.use(\"Agg\"); from matplotlib import pyplot as plt; from matplotlib.tri import Triangulation; import numpy as np; from io import BytesIO; tri=Triangulation([0,1,0,1],[0,0,1,1]); assert tri.triangles.shape==(2,3); assert tri.get_trifinder()(0.2,0.3)>=0; fig,ax=plt.subplots(); ax.imshow(np.array([[0.,1.],[1.,2.]])); ax.contour([[0.,1.],[1.,2.]]); ax.plot([0,1],[1,0]); ax.set_title(r\"Math $x^2$ and fonts\"); png=BytesIO(); fig.savefig(png,format=\"png\"); assert png.getvalue().startswith(bytes([137,80,78,71])); svg=BytesIO(); fig.savefig(svg,format=\"svg\"); assert b\"<svg\" in svg.getvalue(); pdf=BytesIO(); fig.savefig(pdf,format=\"pdf\"); assert pdf.getvalue().startswith(b\"%PDF\"); plt.close(fig); print(\"MATPLOTLIB_REENTRY_3_OK\",matplotlib.__version__)'",
   @"python3 -c 'from importlib.metadata import version, requires; assert version(\"numpy\")==\"2.3.1\"; assert version(\"scipy\")==\"1.16.1\"; assert any(x.startswith(\"numpy\") for x in requires(\"scipy\")); print(\"NATIVE_METADATA_OK\")'",
   @"python3 -c 'from lxml import etree, html, objectify; from lxml.builder import E; from lxml.html.clean import clean_html; assert \"<script\" not in clean_html(\"<div><script>x</script><p>ok</p></div>\"); x=etree.fromstring(b\"<root><item>42</item></root>\"); assert x.xpath(\"string(item)\")==\"42\"; t=etree.XML(b\"<xsl:stylesheet xmlns:xsl=\\\"http://www.w3.org/1999/XSL/Transform\\\" version=\\\"1.0\\\"><xsl:template match=\\\"/\\\"><out><xsl:value-of select=\\\"root/item\\\"/></out></xsl:template></xsl:stylesheet>\"); assert etree.XSLT(t)(x).getroot().text==\"42\"; assert objectify.fromstring(b\"<x>42</x>\")==42; assert html.fromstring(\"<p>ok</p>\").text==\"ok\"; assert E.root().tag==\"root\"; print(\"LXML_REENTRY_1_OK\")'",
   @"python3 -c 'from lxml import etree, html, objectify; from lxml.builder import E; from lxml.html.clean import clean_html; assert \"<script\" not in clean_html(\"<div><script>x</script><p>ok</p></div>\"); x=etree.fromstring(b\"<root><item>42</item></root>\"); assert x.xpath(\"string(item)\")==\"42\"; t=etree.XML(b\"<xsl:stylesheet xmlns:xsl=\\\"http://www.w3.org/1999/XSL/Transform\\\" version=\\\"1.0\\\"><xsl:template match=\\\"/\\\"><out><xsl:value-of select=\\\"root/item\\\"/></out></xsl:template></xsl:stylesheet>\"); assert etree.XSLT(t)(x).getroot().text==\"42\"; assert objectify.fromstring(b\"<x>42</x>\")==42; assert html.fromstring(\"<p>ok</p>\").text==\"ok\"; assert E.root().tag==\"root\"; print(\"LXML_REENTRY_2_OK\")'",
   @"python3 -c 'from lxml import etree, html, objectify; from lxml.builder import E; from lxml.html.clean import clean_html; assert \"<script\" not in clean_html(\"<div><script>x</script><p>ok</p></div>\"); x=etree.fromstring(b\"<root><item>42</item></root>\"); assert x.xpath(\"string(item)\")==\"42\"; t=etree.XML(b\"<xsl:stylesheet xmlns:xsl=\\\"http://www.w3.org/1999/XSL/Transform\\\" version=\\\"1.0\\\"><xsl:template match=\\\"/\\\"><out><xsl:value-of select=\\\"root/item\\\"/></out></xsl:template></xsl:stylesheet>\"); assert etree.XSLT(t)(x).getroot().text==\"42\"; assert objectify.fromstring(b\"<x>42</x>\")==42; assert html.fromstring(\"<p>ok</p>\").text==\"ok\"; assert E.root().tag==\"root\"; print(\"LXML_REENTRY_3_OK\")'",
   @"python3 -c 'import contourpy, numpy as np; g=contourpy.contour_generator(z=np.array([[0.,1.],[1.,2.]])); lines=g.lines(1.); assert len(lines)==1 and lines[0].shape[1]==2; print(\"CONTOURPY_REENTRY_1_OK\")'",
   @"python3 -c 'import contourpy, numpy as np; g=contourpy.contour_generator(z=np.array([[0.,1.],[1.,2.]])); lines=g.lines(1.); assert len(lines)==1 and lines[0].shape[1]==2; print(\"CONTOURPY_REENTRY_2_OK\")'",
   @"python3 -c 'import contourpy, numpy as np; g=contourpy.contour_generator(z=np.array([[0.,1.],[1.,2.]])); lines=g.lines(1.); assert len(lines)==1 and lines[0].shape[1]==2; print(\"CONTOURPY_REENTRY_3_OK\")'",
   @"python3 -c 'import regex; assert regex.findall(r\"\\p{L}+\", \"naïve 東京 123\")==[\"naïve\",\"東京\"]; assert regex.fullmatch(r\"(a(?1)?b)\",\"aaabbb\"); print(\"REGEX_REENTRY_1_OK\")'",
   @"python3 -c 'import regex; assert regex.findall(r\"\\p{L}+\", \"naïve 東京 123\")==[\"naïve\",\"東京\"]; assert regex.fullmatch(r\"(a(?1)?b)\",\"aaabbb\"); print(\"REGEX_REENTRY_2_OK\")'",
   @"python3 -c 'import regex; assert regex.findall(r\"\\p{L}+\", \"naïve 東京 123\")==[\"naïve\",\"東京\"]; assert regex.fullmatch(r\"(a(?1)?b)\",\"aaabbb\"); print(\"REGEX_REENTRY_3_OK\")'",
   @"python3 -c 'from Crypto.Cipher import AES; from Crypto.Hash import SHA256; from Crypto.PublicKey import RSA; key=RSA.generate(1024); assert RSA.import_key(key.export_key()).n==key.n; a=AES.new(bytes(16),AES.MODE_ECB); assert a.decrypt(a.encrypt(bytes(16)))==bytes(16); assert len(SHA256.new(b\"test\").digest())==32; print(\"CRYPTO_OK\")'",
   @"python3 -c 'from Cryptodome.Cipher import AES; from Cryptodome.Hash import SHA256; from Cryptodome.PublicKey import RSA; key=RSA.generate(1024); assert RSA.import_key(key.export_key()).n==key.n; a=AES.new(bytes(16),AES.MODE_ECB); assert a.decrypt(a.encrypt(bytes(16)))==bytes(16); assert len(SHA256.new(b\"test\").digest())==32; print(\"CRYPTODOME_OK\")'",
   @"python3 -c 'from Crypto.Cipher import AES; from Crypto.Hash import SHA256; from Crypto.PublicKey import RSA; key=RSA.generate(1024); assert RSA.import_key(key.export_key()).n==key.n; a=AES.new(bytes(16),AES.MODE_ECB); assert a.decrypt(a.encrypt(bytes(16)))==bytes(16); assert len(SHA256.new(b\"test\").digest())==32; print(\"CRYPTO_OK\")'",
   @"python3 -c 'import scipy, numpy as np; from scipy import linalg, integrate, special, optimize, sparse, stats; assert np.allclose(linalg.solve([[3.,1.],[1.,2.]],[9.,8.]),[2.,3.]); assert abs(integrate.quad(lambda x:x*x,0,1)[0]-1/3)<1e-10; assert special.erf(0)==0; assert abs(stats.norm.cdf(0)-0.5)<1e-10; r=optimize.linprog([1.,1.],bounds=[(1,None),(2,None)],method=\"highs\"); assert r.success and np.allclose(r.x,[1,2]); assert abs(sparse.linalg.eigs(sparse.diags([1.,2.,3.,4.]),k=1,which=\"LM\")[0][0]-4)<1e-6; print(\"SCIPY_OK\", scipy.__version__)'",
   @"python3 -c 'import numpy as np; from scipy.sparse.linalg import svds; ds=[np.float32,np.float64,np.complex64,np.complex128]; values=[svds(np.diag(np.array([1,2,3,4],dtype=d)),k=2,solver=\"propack\",return_singular_vectors=False) for d in ds]; assert all(np.allclose(x,[3,4],atol=1e-4) for x in values); print(\"SCIPY_PROPACK_TYPES_OK\")'",
   @"python3 -c 'from scipy.integrate import quad; from scipy.optimize import minimize, linprog; assert linprog([1.], bounds=[(2,None)], method=\"highs\").success; assert abs(quad(lambda x:x*x,0,1)[0]-1/3)<1e-10; r=minimize(lambda x:(x[0]-3)**2,[0.]); assert r.success; print(\"SCIPY_REPEAT_OK\")'",

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
