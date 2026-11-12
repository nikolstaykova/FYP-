import 'package:http/http.dart' as http;

/// On the web the browser handles certificates (the app is served by the parts server itself).
http.Client makeClient() => http.Client();

void trustLocalServer() {}
