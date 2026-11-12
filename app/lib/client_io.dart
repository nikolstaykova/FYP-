import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http/io_client.dart';

/// The parts server on the home Wi-Fi uses a self-signed certificate. The app trusts it only on private
/// addresses (this Mac, the local network); anything on the internet must have a real certificate.
http.Client makeClient() {
  final c = HttpClient()..connectionTimeout = const Duration(seconds: 10);
  c.badCertificateCallback = (cert, host, port) => isPrivateHost(host);
  return IOClient(c);
}

bool isPrivateHost(String h) =>
    h == 'localhost' ||
    h.endsWith('.local') ||
    h.startsWith('127.') ||
    h.startsWith('10.') ||
    h.startsWith('192.168.') ||
    RegExp(r'^172\.(1[6-9]|2\d|3[01])\.').hasMatch(h);
