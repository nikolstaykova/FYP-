// Parts Quest: choose a lesson, find its parts, show them to the camera.
import 'package:material_ui/material_ui.dart';
import 'package:flutter/services.dart';

import 'api.dart';
import 'client_stub.dart' if (dart.library.io) 'client_io.dart';
import 'pip/pip.dart';
import 'screens/connect.dart';
import 'screens/home.dart';
import 'theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(statusBarColor: Colors.transparent));
  trustLocalServer();
  await Api.instance.load();
  await Pip.loadMe();
  runApp(const PartsQuestApp());
}

class PartsQuestApp extends StatelessWidget {
  const PartsQuestApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Parts Quest',
        debugShowCheckedModeBanner: false,
        theme: buildTheme(Brightness.light),
        darkTheme: buildTheme(Brightness.dark),
        home: Api.instance.ready ? const HomeScreen() : const ConnectScreen(),
      );
}
