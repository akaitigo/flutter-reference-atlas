// SPDX-License-Identifier: Apache-2.0

import Flutter
import UIKit

final class HostViewController: UIViewController {
  private let engine = FlutterEngine(name: "reference_atlas_engine")

  override func viewDidLoad() {
    super.viewDidLoad()
    engine.run()
  }

  func presentFlutter() {
    let flutterViewController = FlutterViewController(
      engine: engine,
      nibName: nil,
      bundle: nil
    )
    present(flutterViewController, animated: true)
  }
}
