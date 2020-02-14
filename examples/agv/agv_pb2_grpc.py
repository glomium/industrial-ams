# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
import grpc

import agv_pb2 as agv__pb2
from google.protobuf import empty_pb2 as google_dot_protobuf_dot_empty__pb2


class SourceStub(object):
  # missing associated documentation comment in .proto file
  pass

  def __init__(self, channel):
    """Constructor.

    Args:
      channel: A grpc.Channel.
    """
    self.get_coordinate = channel.unary_unary(
        '/agv.proto.Source/get_coordinate',
        request_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
        response_deserializer=agv__pb2.Data.FromString,
        )
    self.next_order = channel.unary_unary(
        '/agv.proto.Source/next_order',
        request_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
        response_deserializer=agv__pb2.Time.FromString,
        )
    self.get_part = channel.unary_unary(
        '/agv.proto.Source/get_part',
        request_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
        response_deserializer=agv__pb2.Data.FromString,
        )


class SourceServicer(object):
  # missing associated documentation comment in .proto file
  pass

  def get_coordinate(self, request, context):
    """
    loads coordinates of source
    """
    context.set_code(grpc.StatusCode.UNIMPLEMENTED)
    context.set_details('Method not implemented!')
    raise NotImplementedError('Method not implemented!')

  def next_order(self, request, context):
    """
    returns the time when the next order in queue was created (first come first serve)
    """
    context.set_code(grpc.StatusCode.UNIMPLEMENTED)
    context.set_details('Method not implemented!')
    raise NotImplementedError('Method not implemented!')

  def get_part(self, request, context):
    """
    loads the next part to the carrier
    """
    context.set_code(grpc.StatusCode.UNIMPLEMENTED)
    context.set_details('Method not implemented!')
    raise NotImplementedError('Method not implemented!')


def add_SourceServicer_to_server(servicer, server):
  rpc_method_handlers = {
      'get_coordinate': grpc.unary_unary_rpc_method_handler(
          servicer.get_coordinate,
          request_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
          response_serializer=agv__pb2.Data.SerializeToString,
      ),
      'next_order': grpc.unary_unary_rpc_method_handler(
          servicer.next_order,
          request_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
          response_serializer=agv__pb2.Time.SerializeToString,
      ),
      'get_part': grpc.unary_unary_rpc_method_handler(
          servicer.get_part,
          request_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
          response_serializer=agv__pb2.Data.SerializeToString,
      ),
  }
  generic_handler = grpc.method_handlers_generic_handler(
      'agv.proto.Source', rpc_method_handlers)
  server.add_generic_rpc_handlers((generic_handler,))


class SinkStub(object):
  # missing associated documentation comment in .proto file
  pass

  def __init__(self, channel):
    """Constructor.

    Args:
      channel: A grpc.Channel.
    """
    self.get_coordinate = channel.unary_unary(
        '/agv.proto.Sink/get_coordinate',
        request_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
        response_deserializer=agv__pb2.Data.FromString,
        )
    self.put_part = channel.unary_unary(
        '/agv.proto.Sink/put_part',
        request_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
        response_deserializer=agv__pb2.Time.FromString,
        )


class SinkServicer(object):
  # missing associated documentation comment in .proto file
  pass

  def get_coordinate(self, request, context):
    """
    loads coordinates of sink
    """
    context.set_code(grpc.StatusCode.UNIMPLEMENTED)
    context.set_details('Method not implemented!')
    raise NotImplementedError('Method not implemented!')

  def put_part(self, request, context):
    """
    puts a part into the sink. if it is full it returns a time to wait
    """
    context.set_code(grpc.StatusCode.UNIMPLEMENTED)
    context.set_details('Method not implemented!')
    raise NotImplementedError('Method not implemented!')


def add_SinkServicer_to_server(servicer, server):
  rpc_method_handlers = {
      'get_coordinate': grpc.unary_unary_rpc_method_handler(
          servicer.get_coordinate,
          request_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
          response_serializer=agv__pb2.Data.SerializeToString,
      ),
      'put_part': grpc.unary_unary_rpc_method_handler(
          servicer.put_part,
          request_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
          response_serializer=agv__pb2.Time.SerializeToString,
      ),
  }
  generic_handler = grpc.method_handlers_generic_handler(
      'agv.proto.Sink', rpc_method_handlers)
  server.add_generic_rpc_handlers((generic_handler,))


class VehicleStub(object):
  # missing associated documentation comment in .proto file
  pass

  def __init__(self, channel):
    """Constructor.

    Args:
      channel: A grpc.Channel.
    """
    self.get_coordinate = channel.unary_unary(
        '/agv.proto.Vehicle/get_coordinate',
        request_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
        response_deserializer=agv__pb2.Data.FromString,
        )
    self.drive = channel.unary_unary(
        '/agv.proto.Vehicle/drive',
        request_serializer=agv__pb2.Data.SerializeToString,
        response_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
        )


class VehicleServicer(object):
  # missing associated documentation comment in .proto file
  pass

  def get_coordinate(self, request, context):
    """
    loads coordinates of vehicle, if vehicle is idle, otherwise returns a not available error (closes vehicle first)
    """
    context.set_code(grpc.StatusCode.UNIMPLEMENTED)
    context.set_details('Method not implemented!')
    raise NotImplementedError('Method not implemented!')

  def drive(self, request, context):
    """
    drive to requested position and pickup a workpiece
    """
    context.set_code(grpc.StatusCode.UNIMPLEMENTED)
    context.set_details('Method not implemented!')
    raise NotImplementedError('Method not implemented!')


def add_VehicleServicer_to_server(servicer, server):
  rpc_method_handlers = {
      'get_coordinate': grpc.unary_unary_rpc_method_handler(
          servicer.get_coordinate,
          request_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
          response_serializer=agv__pb2.Data.SerializeToString,
      ),
      'drive': grpc.unary_unary_rpc_method_handler(
          servicer.drive,
          request_deserializer=agv__pb2.Data.FromString,
          response_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
      ),
  }
  generic_handler = grpc.method_handlers_generic_handler(
      'agv.proto.Vehicle', rpc_method_handlers)
  server.add_generic_rpc_handlers((generic_handler,))
